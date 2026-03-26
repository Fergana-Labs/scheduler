'use client';

import { Fragment, useEffect, useState, useCallback } from 'react';
import { Loader2, Search, ChevronDown, ChevronRight } from 'lucide-react';
import { api, captureSessionFromURL, clearSession } from '@/lib/api';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

// --- Types ---

interface FunnelRow {
  week: string;
  page_views: number;
  signup_clicks: number;
  signups: number;
  onboarded: number;
  first_draft_sent: number;
}

interface CohortRow {
  week: string;
  size: number;
  retention: (number | null)[];
  lifetime_actions: (number | null)[];
}

interface TimeSeriesPoint {
  week: string;
  [cohortWeek: string]: string | number;
}

interface CohortData {
  cohorts: CohortRow[];
  max_weeks: number;
  emails_by_week: TimeSeriesPoint[];
  active_by_week: TimeSeriesPoint[];
}

interface ThreadMessage {
  role?: string;
  from?: string;
  body?: string;
  subject?: string;
}

interface DraftRow {
  id: string;
  user_email: string;
  original_subject: string;
  original_body: string;
  sent_body: string | null;
  was_edited: boolean | null;
  edit_distance_ratio: number | null;
  chars_added: number | null;
  chars_removed: number | null;
  was_autopilot: boolean;
  composed_at: string;
  sent_at: string | null;
  thread_context: ThreadMessage[];
}

type Tab = 'funnel' | 'cohorts' | 'drafts' | 'definitions';

// --- Helpers ---

const COHORT_COLORS = [
  '#43614a', '#6b9e76', '#a3d4ae', '#2d4a32', '#8bb896',
  '#5c8a65', '#3a7048', '#7ec48a', '#4f7656', '#96c9a0',
];

function formatWeek(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function pct(a: number, b: number): string {
  if (b === 0) return '—';
  const val = (a / b) * 100;
  if (val > 100) return '—'; // numerator > denominator means tracking started at different times
  return `${val.toFixed(1)}%`;
}

// --- Components ---

const WEEK_OPTIONS = [1, 4, 8, 12, 24, 52] as const;

function FunnelSection() {
  const [weeks, setWeeks] = useState<number>(12);
  const [includeCurrent, setIncludeCurrent] = useState(false);
  const [data, setData] = useState<FunnelRow[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params = `weeks=${weeks}${includeCurrent ? '&include_current=true' : ''}`;
    api<{ data: FunnelRow[] }>(`/web/api/v1/admin/funnel?${params}`)
      .then((res) => setData(res.data))
      .finally(() => setLoading(false));
  }, [weeks, includeCurrent]);

  if (loading || !data) {
    return (
      <div className="flex justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    );
  }

  const chartData = data.map((r) => ({
    week: formatWeek(r.week),
    'Page Views': r.page_views,
    'Signup Clicks': r.signup_clicks,
    Signups: r.signups,
    Onboarded: r.onboarded,
    'First Draft Sent': r.first_draft_sent,
  }));

  const totals = data.reduce(
    (acc, r) => ({
      views: acc.views + r.page_views,
      clicks: acc.clicks + r.signup_clicks,
      signups: acc.signups + r.signups,
      onboarded: acc.onboarded + r.onboarded,
      firstDraft: acc.firstDraft + r.first_draft_sent,
    }),
    { views: 0, clicks: 0, signups: 0, onboarded: 0, firstDraft: 0 }
  );

  const stats = [
    { label: 'Page Views', value: totals.views },
    { label: 'Views → Clicks', value: pct(totals.clicks, totals.views) },
    { label: 'Clicks → Signups', value: pct(totals.signups, totals.clicks) },
    { label: 'Signup → Onboarded', value: pct(totals.onboarded, totals.signups) },
    { label: 'Onboarded → Draft', value: pct(totals.firstDraft, totals.onboarded) },
  ];

  return (
    <div>
      <div className="mb-4 flex items-center gap-4">
        <div className="flex gap-1">
          {WEEK_OPTIONS.map((w) => (
            <button
              key={w}
              onClick={() => setWeeks(w)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                weeks === w ? 'bg-[#43614a] text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {w}w
            </button>
          ))}
        </div>
        <label className="flex items-center gap-1.5 text-xs text-gray-600">
          <input
            type="checkbox"
            checked={includeCurrent}
            onChange={(e) => setIncludeCurrent(e.target.checked)}
            className="rounded"
          />
          Include current week
        </label>
      </div>
      <div className="mb-6 flex flex-wrap gap-4">
        {stats.map((s) => (
          <div key={s.label} className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-2.5">
            <div className="text-xs text-gray-500">{s.label}</div>
            <div className="text-xl font-semibold">{s.value}</div>
          </div>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={350}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="week" tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Legend />
          <Bar dataKey="Page Views" fill="#d1d5db" />
          <Bar dataKey="Signup Clicks" fill="#9ca3af" />
          <Bar dataKey="Signups" fill="#43614a" />
          <Bar dataKey="Onboarded" fill="#6b9e76" />
          <Bar dataKey="First Draft Sent" fill="#a3d4ae" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function CohortSection() {
  const [period, setPeriod] = useState<'weekly' | 'daily'>('weekly');
  const [emailsOnly, setEmailsOnly] = useState(false);
  const [includeCurrent, setIncludeCurrent] = useState(false);
  const [data, setData] = useState<CohortData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params = [
      emailsOnly ? 'emails_only=true' : '',
      includeCurrent ? 'include_current=true' : '',
    ].filter(Boolean).join('&');
    const suffix = params ? `&${params}` : '';
    const url = period === 'weekly'
      ? `/web/api/v1/admin/cohorts?weeks=8${suffix}`
      : `/web/api/v1/admin/cohorts/daily?days=7${suffix}`;
    api<CohortData>(url).then(setData).finally(() => setLoading(false));
  }, [period, emailsOnly, includeCurrent]);

  return (
    <div>
      <div className="mb-4 flex items-center gap-4">
        <div className="flex gap-1">
          {(['weekly', 'daily'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                period === p ? 'bg-[#43614a] text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {p === 'weekly' ? 'Weekly Cohorts' : 'Last 7 Days'}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-1.5 text-xs text-gray-600">
          <input
            type="checkbox"
            checked={emailsOnly}
            onChange={(e) => setEmailsOnly(e.target.checked)}
            className="rounded"
          />
          Emails sent only
        </label>
        <label className="flex items-center gap-1.5 text-xs text-gray-600">
          <input
            type="checkbox"
            checked={includeCurrent}
            onChange={(e) => setIncludeCurrent(e.target.checked)}
            className="rounded"
          />
          Include current {period === 'weekly' ? 'week' : 'day'}
        </label>
      </div>
      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-gray-400" /></div>
      ) : data ? (
        <CohortCharts data={data} periodLabel={period === 'weekly' ? 'W' : 'D'} />
      ) : (
        <p className="text-gray-500">No cohort data yet.</p>
      )}
    </div>
  );
}

function CohortCharts({ data, periodLabel }: { data: CohortData; periodLabel: string }) {
  const { cohorts, max_weeks, emails_by_week, active_by_week } = data;
  const [hoveredSeries, setHoveredSeries] = useState<string | null>(null);

  if (cohorts.length === 0) {
    return <p className="text-gray-500">No cohort data yet.</p>;
  }

  const weekOffsets = Array.from({ length: max_weeks }, (_, i) => i);
  const cohortKeys = cohorts.map((c) => formatWeek(c.week));

  // 1. Retention line chart — omit keys entirely for incomplete offsets so lines stop
  const retentionData = weekOffsets.map((offset) => {
    const point: Record<string, unknown> = { week: `${periodLabel}${offset}` };
    cohorts.forEach((c) => {
      const v = c.retention[offset];
      if (v !== null && v !== undefined) point[formatWeek(c.week)] = v;
    });
    return point;
  });

  // Map raw cohort week keys to formatted labels
  const rawCohortKeys = cohorts.map((c) => c.week);
  function remapCohortKeys(point: TimeSeriesPoint): Record<string, unknown> {
    const out: Record<string, unknown> = { week: formatWeek(point.week as string) };
    rawCohortKeys.forEach((raw, i) => {
      out[cohortKeys[i]] = point[raw] ?? 0;
    });
    return out;
  }

  // 2. Emails sent by absolute date (from backend)
  const emailsData = emails_by_week.map(remapCohortKeys);

  // 3. Active users by absolute date (from backend)
  const activeData = active_by_week.map(remapCohortKeys);

  // 4. Avg cumulative actions — omit keys for incomplete offsets
  const lifetimeData = weekOffsets.map((offset) => {
    const point: Record<string, unknown> = { week: `${periodLabel}${offset}` };
    cohorts.forEach((c) => {
      const v = c.lifetime_actions[offset];
      if (v !== null && v !== undefined) point[formatWeek(c.week)] = v;
    });
    return point;
  });

  // Tooltip that shows only the hovered series
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const FocusedTooltip = ({ active, payload, label, suffix }: any) => {
    if (!active || !payload?.length) return null;
    const item = hoveredSeries
      ? payload.find((p: { dataKey: string }) => p.dataKey === hoveredSeries) || payload[0]
      : payload[0];
    if (item.value === undefined || item.value === null) return null;
    return (
      <div className="rounded border border-gray-200 bg-white px-3 py-2 text-xs shadow-sm">
        <div className="text-gray-500">{label}</div>
        <div className="mt-1 font-medium" style={{ color: item.color }}>
          {item.name}: {item.value}{suffix || ''}
        </div>
      </div>
    );
  };

  // Tooltip that shows hovered series + total (for stacked area charts)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const FocusedTooltipWithTotal = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;
    const item = hoveredSeries
      ? payload.find((p: { dataKey: string }) => p.dataKey === hoveredSeries) || payload[0]
      : payload[0];
    const total = payload.reduce((sum: number, p: { value?: number }) => sum + (p.value || 0), 0);
    return (
      <div className="rounded border border-gray-200 bg-white px-3 py-2 text-xs shadow-sm">
        <div className="text-gray-500">{label}</div>
        <div className="mt-1 font-medium" style={{ color: item.color }}>
          {item.name}: {item.value}
        </div>
        <div className="mt-0.5 text-gray-500">Total: {total}</div>
      </div>
    );
  };

  const handleMouseEnter = (key: string) => () => setHoveredSeries(key);
  const handleMouseLeave = () => setHoveredSeries(null);

  return (
    <div className="space-y-10">
      <section>
        <h3 className="mb-3 text-sm font-medium text-gray-700">User Retention by Week Cohort</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={retentionData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="week" tick={{ fontSize: 12 }} />
            <YAxis unit="%" domain={[0, 100]} />
            <Tooltip content={<FocusedTooltip suffix="%" />} />
            <Legend onMouseEnter={(e) => setHoveredSeries(e.dataKey as string)} onMouseLeave={handleMouseLeave} />
            {cohortKeys.map((key, i) => (
              <Line key={key} type="monotone" dataKey={key} stroke={COHORT_COLORS[i % COHORT_COLORS.length]} strokeWidth={hoveredSeries === key ? 3 : hoveredSeries ? 1 : 2} dot={false} activeDot={{ r: 4 }} onMouseEnter={handleMouseEnter(key)} onMouseLeave={handleMouseLeave} connectNulls={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </section>

      <section>
        <h3 className="mb-3 text-sm font-medium text-gray-700">Total Emails Sent by Week Cohort</h3>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={emailsData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="week" tick={{ fontSize: 12 }} />
            <YAxis allowDecimals={false} />
            <Tooltip content={<FocusedTooltipWithTotal />} />
            <Legend onMouseEnter={(e) => setHoveredSeries(e.dataKey as string)} onMouseLeave={handleMouseLeave} />
            {cohortKeys.map((key, i) => (
              <Area key={key} type="monotone" dataKey={key} stackId="emails" fill={COHORT_COLORS[i % COHORT_COLORS.length]} stroke={COHORT_COLORS[i % COHORT_COLORS.length]} fillOpacity={hoveredSeries === key ? 0.8 : hoveredSeries ? 0.3 : 0.6} activeDot={{ r: 4 }} onMouseEnter={handleMouseEnter(key)} onMouseLeave={handleMouseLeave} />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </section>

      <section>
        <h3 className="mb-3 text-sm font-medium text-gray-700">Active Users by Week Cohort</h3>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={activeData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="week" tick={{ fontSize: 12 }} />
            <YAxis allowDecimals={false} />
            <Tooltip content={<FocusedTooltipWithTotal />} />
            <Legend onMouseEnter={(e) => setHoveredSeries(e.dataKey as string)} onMouseLeave={handleMouseLeave} />
            {cohortKeys.map((key, i) => (
              <Area key={key} type="monotone" dataKey={key} stackId="active" fill={COHORT_COLORS[i % COHORT_COLORS.length]} stroke={COHORT_COLORS[i % COHORT_COLORS.length]} fillOpacity={hoveredSeries === key ? 0.8 : hoveredSeries ? 0.3 : 0.6} activeDot={{ r: 4 }} onMouseEnter={handleMouseEnter(key)} onMouseLeave={handleMouseLeave} />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </section>

      <section>
        <h3 className="mb-3 text-sm font-medium text-gray-700">Avg Cumulative Actions per User by Week Cohort</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={lifetimeData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="week" tick={{ fontSize: 12 }} />
            <YAxis />
            <Tooltip content={<FocusedTooltip />} />
            <Legend onMouseEnter={(e) => setHoveredSeries(e.dataKey as string)} onMouseLeave={handleMouseLeave} />
            {cohortKeys.map((key, i) => (
              <Line key={key} type="monotone" dataKey={key} stroke={COHORT_COLORS[i % COHORT_COLORS.length]} strokeWidth={hoveredSeries === key ? 3 : hoveredSeries ? 1 : 2} dot={false} activeDot={{ r: 4 }} onMouseEnter={handleMouseEnter(key)} onMouseLeave={handleMouseLeave} connectNulls={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </section>
    </div>
  );
}

interface DraftStats {
  total_drafts: number;
  total_sent: number;
  total_edited: number;
  avg_edit_pct: number | null;
  avg_chars_added: number | null;
  avg_chars_removed: number | null;
  total_autopilot: number;
  autopilot_sent: number;
}

function DraftBrowser() {
  const [drafts, setDrafts] = useState<DraftRow[]>([]);
  const [stats, setStats] = useState<DraftStats | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [emailSearch, setEmailSearch] = useState('');
  const [editedOnly, setEditedOnly] = useState(false);
  const [autopilotOnly, setAutopilotOnly] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const perPage = 20;

  useEffect(() => {
    api<DraftStats>('/web/api/v1/admin/drafts/stats').then(setStats).catch(() => {});
  }, []);

  const fetchDrafts = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        per_page: String(perPage),
      });
      if (emailSearch) params.set('email', emailSearch);
      if (editedOnly) params.set('edited_only', 'true');
      if (autopilotOnly) params.set('autopilot_only', 'true');

      const res = await api<{ drafts: DraftRow[]; total: number }>(
        `/web/api/v1/admin/drafts?${params.toString()}`
      );
      setDrafts(res.drafts);
      setTotal(res.total);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [page, emailSearch, editedOnly, autopilotOnly]);

  useEffect(() => {
    fetchDrafts();
  }, [fetchDrafts]);

  const totalPages = Math.ceil(total / perPage);

  return (
    <div>
      {stats && (
        <div className="mb-6 flex flex-wrap gap-4">
          <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-2.5">
            <div className="text-xs text-gray-500">Total Drafts</div>
            <div className="text-xl font-semibold">{stats.total_drafts}</div>
          </div>
          <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-2.5">
            <div className="text-xs text-gray-500">Drafts Sent</div>
            <div className="text-xl font-semibold">{stats.total_sent}</div>
          </div>
          <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-2.5">
            <div className="text-xs text-gray-500">% Sent</div>
            <div className="text-xl font-semibold">{stats.total_drafts > 0 ? `${((stats.total_sent / stats.total_drafts) * 100).toFixed(1)}%` : '—'}</div>
          </div>
          <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-2.5">
            <div className="text-xs text-gray-500">Edited Before Send</div>
            <div className="text-xl font-semibold">{stats.total_edited}</div>
          </div>
          <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-2.5">
            <div className="text-xs text-gray-500">Avg Edit %</div>
            <div className="text-xl font-semibold">{stats.avg_edit_pct !== null ? `${(stats.avg_edit_pct * 100).toFixed(1)}%` : '—'}</div>
          </div>
          <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-2.5">
            <div className="text-xs text-gray-500">Autopilot Sent</div>
            <div className="text-xl font-semibold">{stats.autopilot_sent} / {stats.total_autopilot}</div>
          </div>
        </div>
      )}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search by email..."
            value={emailSearch}
            onChange={(e) => { setEmailSearch(e.target.value); setPage(1); }}
            className="rounded-lg border border-gray-300 py-2 pl-9 pr-3 text-sm focus:border-[#43614a] focus:outline-none"
          />
        </div>
        <label className="flex items-center gap-1.5 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={editedOnly}
            onChange={(e) => { setEditedOnly(e.target.checked); setPage(1); }}
            className="rounded"
          />
          Edited only
        </label>
        <label className="flex items-center gap-1.5 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={autopilotOnly}
            onChange={(e) => { setAutopilotOnly(e.target.checked); setPage(1); }}
            className="rounded"
          />
          Autopilot only
        </label>
        <span className="text-sm text-gray-400">{total} drafts</span>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="w-8 px-2 py-2" />
                <th className="px-3 py-2 text-left font-medium text-gray-600">User</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Subject</th>
                <th className="px-3 py-2 text-center font-medium text-gray-600">Edited</th>
                <th className="px-3 py-2 text-center font-medium text-gray-600">Edit %</th>
                <th className="px-3 py-2 text-center font-medium text-gray-600">Autopilot</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Composed</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Sent</th>
              </tr>
            </thead>
            <tbody>
              {drafts.map((d) => (
                <Fragment key={d.id}>
                  <tr
                    className="cursor-pointer border-b border-gray-100 hover:bg-gray-50"
                    onClick={() => setExpandedId(expandedId === d.id ? null : d.id)}
                  >
                    <td className="px-2 py-2">
                      {expandedId === d.id ? (
                        <ChevronDown className="h-4 w-4 text-gray-400" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-gray-400" />
                      )}
                    </td>
                    <td className="px-3 py-2 text-gray-700">{d.user_email}</td>
                    <td className="max-w-xs truncate px-3 py-2 text-gray-700">{d.original_subject || '(no subject)'}</td>
                    <td className="px-3 py-2 text-center">
                      {d.was_edited === null ? '—' : d.was_edited ? (
                        <span className="rounded bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-800">Yes</span>
                      ) : (
                        <span className="rounded bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">No</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-center text-gray-600">
                      {d.edit_distance_ratio !== null ? `${(d.edit_distance_ratio * 100).toFixed(1)}%` : '—'}
                    </td>
                    <td className="px-3 py-2 text-center">
                      {d.was_autopilot ? (
                        <span className="rounded bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800">Auto</span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-gray-500">{new Date(d.composed_at).toLocaleDateString()}</td>
                    <td className="px-3 py-2 text-gray-500">{d.sent_at ? new Date(d.sent_at).toLocaleDateString() : '—'}</td>
                  </tr>
                  {expandedId === d.id && (
                    <tr className="border-b border-gray-100 bg-gray-50">
                      <td colSpan={8} className="px-6 py-4">
                        {/* Email thread context */}
                        {d.thread_context && d.thread_context.length > 0 && (
                          <div className="mb-4">
                            <div className="mb-2 text-xs font-medium uppercase text-gray-500">Email Thread</div>
                            <div className="space-y-2">
                              {d.thread_context.map((msg, idx) => (
                                <div key={idx} className="rounded border border-gray-200 bg-white p-3">
                                  <div className="mb-1 flex items-center gap-2 text-xs text-gray-500">
                                    <span className="font-medium text-gray-700">{msg.from || msg.role || 'Unknown'}</span>
                                    {msg.subject && <span>&middot; {msg.subject}</span>}
                                  </div>
                                  <pre className="max-h-40 overflow-auto whitespace-pre-wrap text-xs text-gray-600">
                                    {msg.body || '(empty)'}
                                  </pre>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {/* Draft vs sent comparison */}
                        <div className="grid gap-4 md:grid-cols-2">
                          <div>
                            <div className="mb-1 text-xs font-medium uppercase text-gray-500">Original Draft</div>
                            <pre className="max-h-60 overflow-auto whitespace-pre-wrap rounded border border-gray-200 bg-white p-3 text-xs text-gray-700">
                              {d.original_body || '(empty)'}
                            </pre>
                          </div>
                          <div>
                            <div className="mb-1 text-xs font-medium uppercase text-gray-500">Sent Version</div>
                            <pre className="max-h-60 overflow-auto whitespace-pre-wrap rounded border border-gray-200 bg-white p-3 text-xs text-gray-700">
                              {d.sent_body || '(not sent yet)'}
                            </pre>
                          </div>
                        </div>
                        {d.chars_added !== null && (
                          <div className="mt-3 flex gap-4 text-xs text-gray-500">
                            <span className="text-green-600">+{d.chars_added} added</span>
                            <span className="text-red-600">-{d.chars_removed} removed</span>
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-sm text-gray-500">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

function Definitions() {
  return (
    <div className="space-y-8 text-sm text-gray-700 leading-relaxed">
      <section>
        <h3 className="text-base font-semibold text-gray-800 mb-3">Funnel</h3>
        <p className="mb-3">Shows weekly conversion from landing page visit through activation. Each bar represents one calendar week.</p>
        <dl className="space-y-2">
          <div><dt className="font-medium inline">Page Views</dt> <dd className="inline">— Number of times the landing page was loaded. Tracked anonymously via the <code className="rounded bg-gray-100 px-1 text-xs">page_events</code> table (no user ID required). One page load = one event, includes repeat visits.</dd></div>
          <div><dt className="font-medium inline">Signup Clicks</dt> <dd className="inline">— Number of times the &quot;Get Started&quot; CTA button was clicked on the landing page. Also tracked anonymously. Does not deduplicate — a user clicking twice counts as two.</dd></div>
          <div><dt className="font-medium inline">Signups</dt> <dd className="inline">— New user accounts created, from <code className="rounded bg-gray-100 px-1 text-xs">users.created_at</code>. Counted by the week the account was created, regardless of auth method (Google OAuth or Auth0).</dd></div>
          <div><dt className="font-medium inline">Onboarded</dt> <dd className="inline">— Distinct users who completed onboarding (Gmail connected, calendar synced, guides generated). Counted from <code className="rounded bg-gray-100 px-1 text-xs">onboarding_completed</code> events in <code className="rounded bg-gray-100 px-1 text-xs">analytics_events</code>.</dd></div>
          <div><dt className="font-medium inline">First Draft Sent</dt> <dd className="inline">— Users who sent their first composed draft. Uses the earliest <code className="rounded bg-gray-100 px-1 text-xs">draft_sent</code> event per user, grouped by the week that first send occurred.</dd></div>
        </dl>
        <div className="mt-3 rounded border border-gray-200 bg-gray-50 p-3 text-xs text-gray-500">
          <strong>Conversion rates</strong> in the summary cards are computed over the entire time range (not per-week). E.g., &quot;Clicks → Signups&quot; = total signups / total signup clicks across all visible weeks.
        </div>
      </section>

      <section>
        <h3 className="text-base font-semibold text-gray-800 mb-3">Cohorts</h3>
        <p className="mb-3">Users grouped by signup date. &quot;Weekly Cohorts&quot; groups by the Monday of signup week. &quot;Last 7 Days&quot; groups by exact signup date with daily granularity.</p>
        <dl className="space-y-2">
          <div><dt className="font-medium inline">Cohort Size</dt> <dd className="inline">— Total users who signed up in that period, from <code className="rounded bg-gray-100 px-1 text-xs">users.created_at</code>.</dd></div>
          <div><dt className="font-medium inline">Active User</dt> <dd className="inline">— A user with at least one <code className="rounded bg-gray-100 px-1 text-xs">user_created</code>, <code className="rounded bg-gray-100 px-1 text-xs">onboarding_completed</code>, <code className="rounded bg-gray-100 px-1 text-xs">draft_composed</code>, <code className="rounded bg-gray-100 px-1 text-xs">draft_sent</code>, <code className="rounded bg-gray-100 px-1 text-xs">email_classified</code>, or <code className="rounded bg-gray-100 px-1 text-xs">setting_changed</code> event in that time bucket. Signing up and completing onboarding count as activity, so all users are active in their signup period.</dd></div>
        </dl>

        <h4 className="font-medium text-gray-800 mt-4 mb-2">Charts</h4>
        <dl className="space-y-2">
          <div><dt className="font-medium inline">User Retention</dt> <dd className="inline">— Percentage of the cohort that was active in each subsequent period (W0, W1, ... or D0, D1, ...). W0/D0 is always 100% by definition (the user existed). X-axis is time since signup, not calendar date.</dd></div>
          <div><dt className="font-medium inline">Total Emails Sent</dt> <dd className="inline">— Count of <code className="rounded bg-gray-100 px-1 text-xs">draft_sent</code> events per cohort, plotted on a calendar date x-axis. Stacked area — each layer is one cohort.</dd></div>
          <div><dt className="font-medium inline">Active Users</dt> <dd className="inline">— Distinct users with any qualifying event per cohort, plotted on calendar dates. Stacked area.</dd></div>
          <div><dt className="font-medium inline">Avg Cumulative Actions per User</dt> <dd className="inline">— Running total of all qualifying events, divided by <strong>cohort size</strong> (not active users). This means inactive users drag the average down. A cohort of 5 where 1 user has 3 actions shows 0.6, not 3.0. X-axis is time since signup.</dd></div>
        </dl>
      </section>

      <section>
        <h3 className="text-base font-semibold text-gray-800 mb-3">Drafts</h3>
        <p className="mb-3">Browse all composed drafts with their thread context, original/sent body comparison, and edit metrics.</p>

        <h4 className="font-medium text-gray-800 mt-4 mb-2">Summary Stats</h4>
        <dl className="space-y-2">
          <div><dt className="font-medium inline">Total Drafts</dt> <dd className="inline">— All rows in <code className="rounded bg-gray-100 px-1 text-xs">composed_drafts</code>. Includes both sent and unsent.</dd></div>
          <div><dt className="font-medium inline">Drafts Sent</dt> <dd className="inline">— Drafts where <code className="rounded bg-gray-100 px-1 text-xs">sent_at</code> is not null. Matched when the user sends any email in the same Gmail thread — the system detects the send via Gmail webhook and links it to the most recent unsent draft for that thread.</dd></div>
          <div><dt className="font-medium inline">% Sent</dt> <dd className="inline">— Drafts Sent / Total Drafts. Measures how often users actually use the drafts we compose.</dd></div>
          <div><dt className="font-medium inline">Edited Before Send</dt> <dd className="inline">— Drafts where the sent body differs from the original by more than 2% (after whitespace normalization). Uses Python&apos;s <code className="rounded bg-gray-100 px-1 text-xs">difflib.SequenceMatcher</code> ratio.</dd></div>
          <div><dt className="font-medium inline">Avg Edit %</dt> <dd className="inline">— Average <code className="rounded bg-gray-100 px-1 text-xs">edit_distance_ratio</code> across all sent drafts. 0% = sent exactly as composed, 100% = completely rewritten. Computed as <code className="rounded bg-gray-100 px-1 text-xs">1 - SequenceMatcher.ratio()</code> on whitespace-normalized text.</dd></div>
          <div><dt className="font-medium inline">Autopilot Sent</dt> <dd className="inline">— Drafts composed in autopilot mode (sent directly without creating a draft). Format: sent / total autopilot drafts.</dd></div>
        </dl>

        <h4 className="font-medium text-gray-800 mt-4 mb-2">Per-Draft Fields</h4>
        <dl className="space-y-2">
          <div><dt className="font-medium inline">Edited</dt> <dd className="inline">— Yes/No based on the 2% threshold after whitespace normalization.</dd></div>
          <div><dt className="font-medium inline">Edit %</dt> <dd className="inline">— <code className="rounded bg-gray-100 px-1 text-xs">edit_distance_ratio * 100</code>. Only shown for sent drafts.</dd></div>
          <div><dt className="font-medium inline">Autopilot</dt> <dd className="inline">— Whether the draft was composed and sent automatically without user review.</dd></div>
          <div><dt className="font-medium inline">Email Thread</dt> <dd className="inline">— Anonymized thread context stored at composition time. PII (names, emails, companies) is stripped via Claude Haiku before storage. Only includes messages up to and including the triggering email.</dd></div>
          <div><dt className="font-medium inline">+N added / -N removed</dt> <dd className="inline">— Character-level diff between original and sent body. Computed from <code className="rounded bg-gray-100 px-1 text-xs">difflib.SequenceMatcher.get_opcodes()</code>.</dd></div>
        </dl>
      </section>

      <section>
        <h3 className="text-base font-semibold text-gray-800 mb-3">Data Sources</h3>
        <dl className="space-y-2">
          <div><dt className="font-medium inline"><code className="rounded bg-gray-100 px-1 text-xs">analytics_events</code></dt> <dd className="inline">— Generic event log. Requires <code className="rounded bg-gray-100 px-1 text-xs">user_id</code>. Events: <code className="rounded bg-gray-100 px-1 text-xs">user_created</code>, <code className="rounded bg-gray-100 px-1 text-xs">email_classified</code>, <code className="rounded bg-gray-100 px-1 text-xs">draft_composed</code>, <code className="rounded bg-gray-100 px-1 text-xs">draft_sent</code>, <code className="rounded bg-gray-100 px-1 text-xs">onboarding_completed</code>, <code className="rounded bg-gray-100 px-1 text-xs">onboarding_failed</code>, <code className="rounded bg-gray-100 px-1 text-xs">setting_changed</code>. Retained for 90 days.</dd></div>
          <div><dt className="font-medium inline"><code className="rounded bg-gray-100 px-1 text-xs">composed_drafts</code></dt> <dd className="inline">— One row per composed draft. Stores anonymized thread context, original and sent body, edit metrics. Retained for 90 days.</dd></div>
          <div><dt className="font-medium inline"><code className="rounded bg-gray-100 px-1 text-xs">page_events</code></dt> <dd className="inline">— Anonymous page-level events (no user ID). Only allows <code className="rounded bg-gray-100 px-1 text-xs">landing_page_view</code> and <code className="rounded bg-gray-100 px-1 text-xs">signup_click</code> via allowlist.</dd></div>
          <div><dt className="font-medium inline"><code className="rounded bg-gray-100 px-1 text-xs">users</code></dt> <dd className="inline">— User accounts. <code className="rounded bg-gray-100 px-1 text-xs">created_at</code> used for cohort grouping and signup counts.</dd></div>
          <div><dt className="font-medium inline">Google Analytics (GA4)</dt> <dd className="inline">— Tracks anonymous page views and UTM attribution on the marketing site. Separate from the admin dashboard — view in the GA4 console.</dd></div>
        </dl>
      </section>
    </div>
  );
}

// --- Main Page ---

export default function AdminDashboard() {
  const [tab, setTab] = useState<Tab>('funnel');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    captureSessionFromURL();
    async function init() {
      try {
        await api('/auth/me');
      } catch (err: unknown) {
        const status = err instanceof Error && 'status' in err ? (err as { status: number }).status : 0;
        if (status === 403) {
          setError('Admin access required');
        } else {
          clearSession();
          window.location.href = `${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/login`;
          return;
        }
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-semibold text-gray-800">{error}</h1>
          <p className="mt-2 text-gray-500">You don&apos;t have permission to view this page.</p>
        </div>
      </div>
    );
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: 'funnel', label: 'Funnel' },
    { key: 'cohorts', label: 'Cohorts' },
    { key: 'drafts', label: 'Drafts' },
    { key: 'definitions', label: 'Definitions' },
  ];

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <h1 className="text-2xl font-semibold text-gray-800">Analytics</h1>
      <div className="mt-6 flex gap-1 border-b border-gray-200">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors ${
              tab === t.key
                ? 'border-b-2 border-[#43614a] text-[#43614a]'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="mt-6">
        {tab === 'funnel' && <FunnelSection />}
        {tab === 'cohorts' && <CohortSection />}
        {tab === 'drafts' && <DraftBrowser />}
        {tab === 'definitions' && <Definitions />}
      </div>
    </div>
  );
}
