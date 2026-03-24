'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface CalendarEntry {
  id: string;
  summary: string;
  primary: boolean;
  selected: boolean;
}

export default function CalendarPicker() {
  const [calendars, setCalendars] = useState<CalendarEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    api<CalendarEntry[]>('/web/api/v1/calendars')
      .then(setCalendars)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function toggleCalendar(id: string) {
    const updated = calendars.map((cal) =>
      cal.id === id ? { ...cal, selected: !cal.selected } : cal,
    );
    setCalendars(updated);

    const selectedIds = updated.filter((c) => c.selected).map((c) => c.id);
    setSaving(true);
    try {
      await api('/web/api/v1/settings/calendars', {
        method: 'PUT',
        body: JSON.stringify({ calendar_ids: selectedIds }),
      });
    } catch {
      // Revert on failure
      setCalendars(calendars);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="rounded-xl border border-gray-100 bg-[#FAFAFA] p-4">
        <p className="text-sm text-gray-400">Loading calendars...</p>
      </div>
    );
  }

  if (calendars.length === 0) return null;

  const selectedCount = calendars.filter((c) => c.selected).length;

  return (
    <div className="rounded-xl border border-gray-100 bg-[#FAFAFA] p-4">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-start justify-between gap-4"
      >
        <div className="text-left">
          <p className="text-sm font-medium text-gray-900">Availability Calendars</p>
          <p className="mt-1 text-xs text-gray-500">
            {selectedCount === 0
              ? 'Only your primary calendar is checked for conflicts.'
              : `${selectedCount} extra calendar${selectedCount > 1 ? 's' : ''} checked for conflicts.`}
          </p>
        </div>
        <span className="mt-0.5 text-xs text-gray-400">{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div className="mt-3 space-y-2">
          {calendars.map((cal) => (
            <label
              key={cal.id}
              className="flex cursor-pointer items-center gap-3 rounded-lg px-2 py-1.5 hover:bg-gray-100"
            >
              <input
                type="checkbox"
                checked={cal.primary || cal.selected}
                disabled={cal.primary || saving}
                onChange={() => toggleCalendar(cal.id)}
                className="h-4 w-4 rounded border-gray-300 text-[#43614a] accent-[#43614a]"
              />
              <span className="text-sm text-gray-700">
                {cal.summary}
                {cal.primary && (
                  <span className="ml-1.5 text-xs text-gray-400">(primary — always included)</span>
                )}
              </span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
