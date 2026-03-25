'use client';

import { useEffect, useState, useCallback } from 'react';
import { Loader2, Search, ChevronDown, ChevronRight } from 'lucide-react';
import { api, captureSessionFromURL, clearSession } from '@/lib/api';
import {
  BarChart,
  Bar,
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
  signups: number;
  onboarded: number;
  first_draft_sent: number;
}

interface CohortRow {
  week: string;
  size: number;
  retention: number[];
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
}

type Tab = 'funnel' | 'cohorts' | 'drafts';

// --- Helpers ---

function formatWeek(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function retentionColor(pct: number): string {
  if (pct >= 60) return 'bg-green-200 text-green-900';
  if (pct >= 40) return 'bg-green-100 text-green-800';
  if (pct >= 20) return 'bg-yellow-100 text-yellow-800';
  if (pct > 0) return 'bg-orange-100 text-orange-800';
  return 'bg-gray-50 text-gray-400';
}

// --- Components ---

function FunnelChart({ data }: { data: FunnelRow[] }) {
  const chartData = data.map((r) => ({
    week: formatWeek(r.week),
    Signups: r.signups,
    Onboarded: r.onboarded,
    'First Draft Sent': r.first_draft_sent,
  }));

  // Compute overall conversion rates
  const totals = data.reduce(
    (acc, r) => ({
      signups: acc.signups + r.signups,
      onboarded: acc.onboarded + r.onboarded,
      firstDraft: acc.firstDraft + r.first_draft_sent,
    }),
    { signups: 0, onboarded: 0, firstDraft: 0 }
  );

  const onboardRate = totals.signups > 0 ? ((totals.onboarded / totals.signups) * 100).toFixed(1) : '—';
  const draftRate = totals.onboarded > 0 ? ((totals.firstDraft / totals.onboarded) * 100).toFixed(1) : '—';

  return (
    <div>
      <div className="mb-6 flex gap-6">
        <div className="rounded-lg border border-gray-200 bg-gray-50 px-5 py-3">
          <div className="text-sm text-gray-500">Total Signups</div>
          <div className="text-2xl font-semibold">{totals.signups}</div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-gray-50 px-5 py-3">
          <div className="text-sm text-gray-500">Signup &rarr; Onboarded</div>
          <div className="text-2xl font-semibold">{onboardRate}%</div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-gray-50 px-5 py-3">
          <div className="text-sm text-gray-500">Onboarded &rarr; First Draft</div>
          <div className="text-2xl font-semibold">{draftRate}%</div>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={350}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="week" tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Legend />
          <Bar dataKey="Signups" fill="#43614a" />
          <Bar dataKey="Onboarded" fill="#6b9e76" />
          <Bar dataKey="First Draft Sent" fill="#a3d4ae" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function CohortTable({ cohorts }: { cohorts: CohortRow[] }) {
  const maxWeeks = Math.max(...cohorts.map((c) => c.retention.length), 0);

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="px-3 py-2 text-left font-medium text-gray-600">Cohort</th>
            <th className="px-3 py-2 text-right font-medium text-gray-600">Users</th>
            {Array.from({ length: maxWeeks }, (_, i) => (
              <th key={i} className="px-3 py-2 text-center font-medium text-gray-600">
                W{i}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cohorts.map((c) => (
            <tr key={c.week} className="border-b border-gray-100">
              <td className="px-3 py-2 font-medium text-gray-700">{formatWeek(c.week)}</td>
              <td className="px-3 py-2 text-right text-gray-600">{c.size}</td>
              {Array.from({ length: maxWeeks }, (_, i) => {
                const pct = c.retention[i] ?? 0;
                return (
                  <td key={i} className="px-1 py-1 text-center">
                    <span className={`inline-block min-w-[3rem] rounded px-2 py-1 text-xs font-medium ${retentionColor(pct)}`}>
                      {pct > 0 ? `${pct}%` : '—'}
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DraftBrowser() {
  const [drafts, setDrafts] = useState<DraftRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [emailSearch, setEmailSearch] = useState('');
  const [editedOnly, setEditedOnly] = useState(false);
  const [autopilotOnly, setAutopilotOnly] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const perPage = 20;

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
                <>
                  <tr
                    key={d.id}
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
                    <tr key={`${d.id}-expanded`} className="border-b border-gray-100 bg-gray-50">
                      <td colSpan={8} className="px-6 py-4">
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
                </>
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

// --- Main Page ---

export default function AdminDashboard() {
  const [tab, setTab] = useState<Tab>('funnel');
  const [funnelData, setFunnelData] = useState<FunnelRow[] | null>(null);
  const [cohortData, setCohortData] = useState<CohortRow[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    captureSessionFromURL();
    async function init() {
      try {
        await api('/auth/me');
        const [funnel, cohorts] = await Promise.all([
          api<{ data: FunnelRow[] }>('/web/api/v1/admin/funnel'),
          api<{ cohorts: CohortRow[] }>('/web/api/v1/admin/cohorts'),
        ]);
        setFunnelData(funnel.data);
        setCohortData(cohorts.cohorts);
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
        {tab === 'funnel' && funnelData && <FunnelChart data={funnelData} />}
        {tab === 'cohorts' && cohortData && <CohortTable cohorts={cohortData} />}
        {tab === 'drafts' && <DraftBrowser />}
      </div>
    </div>
  );
}
