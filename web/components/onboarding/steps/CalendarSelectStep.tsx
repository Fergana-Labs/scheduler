'use client';

import { useEffect, useState } from 'react';
import { Loader2, Check } from 'lucide-react';
import { api } from '@/lib/api';

interface CalendarEntry {
  id: string;
  summary: string;
  primary: boolean;
  selected: boolean;
}

interface CalendarSelectStepProps {
  onContinue: () => void;
}

export default function CalendarSelectStep({ onContinue }: CalendarSelectStepProps) {
  const [calendars, setCalendars] = useState<CalendarEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    api<CalendarEntry[]>('/web/api/v1/calendars')
      .then(setCalendars)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  function toggleCalendar(id: string) {
    setCalendars((prev) =>
      prev.map((cal) =>
        cal.id === id ? { ...cal, selected: !cal.selected } : cal,
      ),
    );
  }

  async function handleContinue() {
    const selectedIds = calendars.filter((c) => c.selected).map((c) => c.id);
    setSaving(true);
    try {
      await api('/web/api/v1/settings/calendars', {
        method: 'PUT',
        body: JSON.stringify({ calendar_ids: selectedIds }),
      });
    } catch {
      // non-critical — proceed anyway
    }
    setSaving(false);
    onContinue();
  }

  if (loading) {
    return (
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Loading your calendars...</h1>
        <div className="mt-8 flex justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
        </div>
      </div>
    );
  }

  if (error || calendars.length === 0) {
    // Skip this step if we can't load calendars
    return (
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Select your calendars</h1>
        <p className="mt-2 text-sm text-gray-500">
          We couldn&apos;t load your calendars right now. You can configure this later in settings.
        </p>
        <button
          onClick={onContinue}
          className="mt-8 inline-flex w-full cursor-pointer items-center justify-center rounded-xl bg-[#43614a] px-6 py-4 text-base font-semibold text-white transition-colors hover:bg-[#527559]"
        >
          Continue
        </button>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-xl font-semibold text-gray-900">
        Which calendars should we check?
      </h1>
      <p className="mt-2 text-sm text-gray-500">
        Scheduled will check these calendars for conflicts when suggesting meeting times.
      </p>

      <div className="mt-6 space-y-2">
        {calendars.map((cal) => (
          <button
            key={cal.id}
            onClick={() => !cal.primary && toggleCalendar(cal.id)}
            disabled={cal.primary}
            className={`flex w-full items-center gap-3 rounded-lg border px-4 py-3 text-left text-sm transition-colors ${
              cal.primary || cal.selected
                ? 'border-[#43614a] bg-[#43614a]/5 text-gray-900'
                : 'cursor-pointer border-gray-200 text-gray-600 hover:border-gray-300'
            } ${cal.primary ? 'cursor-default' : 'cursor-pointer'}`}
          >
            <div
              className={`flex h-4.5 w-4.5 flex-shrink-0 items-center justify-center rounded border ${
                cal.primary || cal.selected
                  ? 'border-[#43614a] bg-[#43614a]'
                  : 'border-gray-300'
              }`}
            >
              {(cal.primary || cal.selected) && (
                <Check className="h-3 w-3 text-white" />
              )}
            </div>
            <div className="flex-1">
              <span>{cal.summary}</span>
              {cal.primary && (
                <span className="ml-1.5 text-xs text-gray-400">(primary)</span>
              )}
            </div>
          </button>
        ))}
      </div>

      <button
        onClick={handleContinue}
        disabled={saving}
        className="mt-8 inline-flex w-full cursor-pointer items-center justify-center rounded-xl bg-[#43614a] px-6 py-4 text-base font-semibold text-white transition-colors hover:bg-[#527559] disabled:opacity-60"
      >
        {saving ? <Loader2 className="h-5 w-5 animate-spin" /> : 'Continue'}
      </button>
    </div>
  );
}
