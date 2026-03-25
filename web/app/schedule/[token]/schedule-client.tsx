'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import {
  Calendar,
  Clock,
  Check,
  AlertCircle,
  Loader2,
  ExternalLink,
  ChevronRight,
  ChevronLeft,
} from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_CONTROL_PLANE_URL;

interface SchedulingLinkData {
  status: string;
  mode: 'suggested' | 'availability';
  host_name: string;
  attendee_name: string | null;
  attendee_email: string | null;
  event_summary: string;
  duration_minutes: number;
  timezone: string;
  suggested_windows: { date: string; start: string; end: string }[];
  location: string;
  add_google_meet: boolean;
  expires_at: string | null;
  confirmed_time_start?: string;
  confirmed_time_end?: string;
}

type PageState =
  | 'loading'
  | 'selecting'
  | 'confirming'
  | 'success'
  | 'submitted'
  | 'expired'
  | 'already_confirmed'
  | 'already_submitted'
  | 'error'
  | 'not_found';

// -- Helpers --

function generateSlots(
  windows: { date: string; start: string; end: string }[],
  durationMinutes: number,
) {
  const slots: { start: Date; end: Date; dateKey: string }[] = [];
  const now = new Date();

  for (const w of windows) {
    const [startH, startM] = w.start.split(':').map(Number);
    const [endH, endM] = w.end.split(':').map(Number);

    const baseDate = new Date(`${w.date}T00:00:00`);
    let cursor = new Date(baseDate);
    cursor.setHours(startH, startM, 0, 0);

    const windowEnd = new Date(baseDate);
    windowEnd.setHours(endH, endM, 0, 0);

    while (cursor.getTime() + durationMinutes * 60000 <= windowEnd.getTime()) {
      const slotStart = new Date(cursor);
      const slotEnd = new Date(cursor.getTime() + durationMinutes * 60000);

      if (slotStart > now) {
        slots.push({ start: slotStart, end: slotEnd, dateKey: w.date });
      }

      cursor = new Date(cursor.getTime() + durationMinutes * 60000);
    }
  }

  return slots;
}

function formatTime(date: Date) {
  return date.toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr + 'T12:00:00');
  return d.toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });
}

function groupByDate<T extends { dateKey: string }>(items: T[]) {
  const groups: Record<string, T[]> = {};
  for (const item of items) {
    if (!groups[item.dateKey]) groups[item.dateKey] = [];
    groups[item.dateKey].push(item);
  }
  return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
}

// -- When2Meet Grid Helpers --

function generateGridDates(days: number = 7): string[] {
  const dates: string[] = [];
  const now = new Date();
  for (let i = 0; i < days; i++) {
    const d = new Date(now);
    d.setDate(d.getDate() + i);
    dates.push(d.toISOString().split('T')[0]);
  }
  return dates;
}

function generateGridTimes(): string[] {
  const times: string[] = [];
  for (let h = 8; h < 20; h++) {
    times.push(`${h.toString().padStart(2, '0')}:00`);
    times.push(`${h.toString().padStart(2, '0')}:30`);
  }
  return times;
}

function formatGridTime(time: string) {
  const [h, m] = time.split(':').map(Number);
  const ampm = h >= 12 ? 'PM' : 'AM';
  const h12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${h12}${m === 0 ? '' : ':30'}${ampm}`;
}

function formatGridDate(dateStr: string) {
  const d = new Date(dateStr + 'T12:00:00');
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}

// -- Components --

function MarketingPanel() {
  return (
    <div className="bg-gray-50 rounded-2xl p-6 sm:p-8 flex flex-col items-center text-center">
      {/* Greyed-out calendar mock */}
      <div className="w-full max-w-xs mb-6">
        <div className="grid grid-cols-7 gap-1 opacity-30">
          {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d, i) => (
            <div key={i} className="text-xs text-gray-500 font-medium py-1">
              {d}
            </div>
          ))}
          {Array.from({ length: 35 }, (_, i) => (
            <div
              key={i}
              className={`aspect-square rounded text-xs flex items-center justify-center ${
                i >= 3 && i <= 33
                  ? 'bg-gray-200 text-gray-400'
                  : 'text-gray-300'
              } ${[8, 12, 15, 22, 26].includes(i) ? 'bg-blue-100 text-blue-300' : ''}`}
            >
              {i >= 3 && i <= 33 ? i - 2 : ''}
            </div>
          ))}
        </div>
      </div>

      <Calendar className="w-8 h-8 text-gray-400 mb-3" />
      <h3 className="text-lg font-semibold text-gray-800 font-[family-name:var(--font-space-grotesk)] mb-2">
        Next time, schedule this automatically
      </h3>
      <p className="text-sm text-gray-500 mb-6 leading-relaxed">
        Let AI handle the back-and-forth. Connect your Google Calendar and
        Scheduled will propose times, check availability, and send invites
        &mdash; all from your inbox.
      </p>
      <a
        href="https://tryscheduled.com"
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 bg-black text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-gray-800 transition-colors"
      >
        Get Started Free
        <ExternalLink className="w-3.5 h-3.5" />
      </a>
    </div>
  );
}

function CalendarPicker({
  windows,
  durationMinutes,
  hostName,
  selectedSlot,
  onSelectSlot,
  onConfirm,
  confirming,
}: {
  windows: { date: string; start: string; end: string }[];
  durationMinutes: number;
  hostName: string;
  selectedSlot: { start: Date; end: Date } | null;
  onSelectSlot: (slot: { start: Date; end: Date }) => void;
  onConfirm: () => void;
  confirming: boolean;
}) {
  const allSlots = generateSlots(windows, durationMinutes);
  const availableDates = new Set(allSlots.map((s) => s.dateKey));
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [viewMonth, setViewMonth] = useState<Date>(() => {
    // Start on the month of the first available date
    if (allSlots.length > 0) {
      return new Date(allSlots[0].start.getFullYear(), allSlots[0].start.getMonth(), 1);
    }
    return new Date(new Date().getFullYear(), new Date().getMonth(), 1);
  });

  // Build calendar grid for the current month
  const year = viewMonth.getFullYear();
  const month = viewMonth.getMonth();
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const monthLabel = viewMonth.toLocaleDateString(undefined, {
    month: 'long',
    year: 'numeric',
  });

  const calendarDays: (number | null)[] = [];
  for (let i = 0; i < firstDay; i++) calendarDays.push(null);
  for (let d = 1; d <= daysInMonth; d++) calendarDays.push(d);

  const toDateKey = (day: number) => {
    const m = (month + 1).toString().padStart(2, '0');
    const d = day.toString().padStart(2, '0');
    return `${year}-${m}-${d}`;
  };

  const slotsForDate = selectedDate
    ? allSlots.filter((s) => s.dateKey === selectedDate)
    : [];

  if (allSlots.length === 0) {
    return (
      <p className="text-gray-500 py-8 text-center">
        No available time slots. Please ask {hostName} for updated times.
      </p>
    );
  }

  return (
    <div className="flex flex-col sm:flex-row gap-6">
      {/* Calendar */}
      <div className="sm:w-72 flex-shrink-0">
        <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-4">
          Select a date
        </h3>
        <div className="border border-gray-200 rounded-xl p-4">
          {/* Month navigation */}
          <div className="flex items-center justify-between mb-4">
            <button
              onClick={() => setViewMonth(new Date(year, month - 1, 1))}
              className="p-1 hover:bg-gray-100 rounded transition-colors"
            >
              <ChevronLeft className="w-4 h-4 text-gray-600" />
            </button>
            <span className="text-sm font-semibold text-gray-800">
              {monthLabel}
            </span>
            <button
              onClick={() => setViewMonth(new Date(year, month + 1, 1))}
              className="p-1 hover:bg-gray-100 rounded transition-colors"
            >
              <ChevronRight className="w-4 h-4 text-gray-600" />
            </button>
          </div>

          {/* Day headers */}
          <div className="grid grid-cols-7 gap-1 mb-1">
            {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((d) => (
              <div
                key={d}
                className="text-center text-xs font-medium text-gray-400 py-1"
              >
                {d}
              </div>
            ))}
          </div>

          {/* Days */}
          <div className="grid grid-cols-7 gap-1">
            {calendarDays.map((day, i) => {
              if (day === null) {
                return <div key={`empty-${i}`} />;
              }
              const dateKey = toDateKey(day);
              const hasSlots = availableDates.has(dateKey);
              const isSelected = selectedDate === dateKey;
              const today = new Date();
              const isPast =
                new Date(year, month, day) <
                new Date(today.getFullYear(), today.getMonth(), today.getDate());

              return (
                <button
                  key={dateKey}
                  onClick={() => hasSlots && !isPast && setSelectedDate(dateKey)}
                  disabled={!hasSlots || isPast}
                  className={`aspect-square rounded-lg flex items-center justify-center text-sm transition-all ${
                    isSelected
                      ? 'bg-black text-white font-semibold'
                      : hasSlots && !isPast
                        ? 'text-gray-900 font-medium hover:bg-gray-100 cursor-pointer'
                        : 'text-gray-300 cursor-default'
                  }`}
                >
                  {day}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Time slots for selected date */}
      <div className="flex-1 min-w-0">
        {!selectedDate ? (
          <div className="flex items-center justify-center h-full min-h-[200px]">
            <p className="text-gray-400 text-sm">
              Select a date to see available times
            </p>
          </div>
        ) : (
          <div>
            <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-4">
              {formatDate(selectedDate)}
            </h3>
            <div className="space-y-2">
              {slotsForDate.map((slot, i) => {
                const isSelected =
                  selectedSlot?.start.getTime() === slot.start.getTime();
                return (
                  <button
                    key={i}
                    onClick={() => onSelectSlot(slot)}
                    disabled={confirming}
                    className={`w-full px-4 py-3 rounded-lg border text-sm font-medium transition-all text-left ${
                      isSelected
                        ? 'border-black bg-black text-white'
                        : 'border-gray-200 text-gray-700 hover:border-gray-400 hover:bg-gray-50 active:bg-gray-100'
                    } disabled:opacity-50`}
                  >
                    {formatTime(slot.start)} &ndash; {formatTime(slot.end)}
                  </button>
                );
              })}
            </div>

            {selectedSlot && selectedSlot.start >= new Date(`${selectedDate}T00:00:00`) && (
              <div className="mt-6 p-4 bg-gray-50 rounded-xl">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-gray-800">
                      {selectedSlot.start.toLocaleDateString(undefined, {
                        weekday: 'long',
                        month: 'long',
                        day: 'numeric',
                      })}
                    </p>
                    <p className="text-sm text-gray-500">
                      {formatTime(selectedSlot.start)} &ndash;{' '}
                      {formatTime(selectedSlot.end)}
                    </p>
                  </div>
                  <button
                    onClick={onConfirm}
                    disabled={confirming}
                    className="inline-flex items-center gap-2 bg-black text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-gray-800 transition-colors disabled:opacity-50 w-full sm:w-auto justify-center"
                  >
                    {confirming ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <ChevronRight className="w-4 h-4" />
                    )}
                    Confirm
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function AvailabilityGrid({
  onSubmit,
  submitting,
}: {
  onSubmit: (availability: { date: string; start: string; end: string }[]) => void;
  submitting: boolean;
}) {
  const dates = generateGridDates(7);
  const times = generateGridTimes();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [isDragging, setIsDragging] = useState(false);
  const [dragMode, setDragMode] = useState<'select' | 'deselect'>('select');
  const gridRef = useRef<HTMLDivElement>(null);

  const cellKey = (date: string, time: string) => `${date}|${time}`;

  const toggleCell = (date: string, time: string, mode?: 'select' | 'deselect') => {
    const key = cellKey(date, time);
    setSelected((prev) => {
      const next = new Set(prev);
      const shouldSelect = mode ? mode === 'select' : !prev.has(key);
      if (shouldSelect) {
        next.add(key);
      } else {
        next.delete(key);
      }
      return next;
    });
  };

  const handleMouseDown = (date: string, time: string) => {
    const key = cellKey(date, time);
    setIsDragging(true);
    const mode = selected.has(key) ? 'deselect' : 'select';
    setDragMode(mode);
    toggleCell(date, time, mode);
  };

  const handleMouseEnter = (date: string, time: string) => {
    if (!isDragging) return;
    toggleCell(date, time, dragMode);
  };

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Touch support
  const getCellFromTouch = useCallback((e: React.TouchEvent) => {
    const touch = e.touches[0];
    if (!touch) return null;
    const el = document.elementFromPoint(touch.clientX, touch.clientY);
    if (!el) return null;
    const date = el.getAttribute('data-date');
    const time = el.getAttribute('data-time');
    if (date && time) return { date, time };
    return null;
  }, []);

  const handleTouchStart = (date: string, time: string) => {
    const key = cellKey(date, time);
    setIsDragging(true);
    const mode = selected.has(key) ? 'deselect' : 'select';
    setDragMode(mode);
    toggleCell(date, time, mode);
  };

  const handleTouchMove = useCallback(
    (e: React.TouchEvent) => {
      if (!isDragging) return;
      e.preventDefault();
      const cell = getCellFromTouch(e);
      if (cell) toggleCell(cell.date, cell.time, dragMode);
    },
    [isDragging, dragMode, getCellFromTouch],
  );

  useEffect(() => {
    window.addEventListener('mouseup', handleMouseUp);
    window.addEventListener('touchend', handleMouseUp);
    return () => {
      window.removeEventListener('mouseup', handleMouseUp);
      window.removeEventListener('touchend', handleMouseUp);
    };
  }, [handleMouseUp]);

  const handleSubmit = () => {
    const availability: { date: string; start: string; end: string }[] = [];
    for (const key of selected) {
      const [date, start] = key.split('|');
      const [h, m] = start.split(':').map(Number);
      const endMin = m + 30;
      const endH = h + Math.floor(endMin / 60);
      const endM = endMin % 60;
      availability.push({
        date,
        start,
        end: `${endH.toString().padStart(2, '0')}:${endM.toString().padStart(2, '0')}`,
      });
    }
    availability.sort((a, b) => `${a.date}${a.start}`.localeCompare(`${b.date}${b.start}`));
    onSubmit(availability);
  };

  return (
    <div>
      <div
        ref={gridRef}
        className="overflow-x-auto select-none touch-none"
        onMouseLeave={() => setIsDragging(false)}
        onTouchMove={handleTouchMove}
      >
        <table className="border-collapse text-xs w-full">
          <thead>
            <tr>
              <th className="sticky left-0 bg-white z-10 px-1 sm:px-2 py-1 w-12 sm:w-16" />
              {dates.map((d) => (
                <th
                  key={d}
                  className="px-0.5 sm:px-1 py-1 text-gray-500 font-medium whitespace-nowrap text-[10px] sm:text-xs"
                >
                  {formatGridDate(d)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {times.map((time) => (
              <tr key={time}>
                <td className="sticky left-0 bg-white z-10 px-1 sm:px-2 py-0.5 text-gray-400 text-right whitespace-nowrap border-r border-gray-100 text-[10px] sm:text-xs">
                  {time.endsWith(':00') ? formatGridTime(time) : ''}
                </td>
                {dates.map((date) => {
                  const key = cellKey(date, time);
                  const isSelected = selected.has(key);
                  return (
                    <td
                      key={key}
                      data-date={date}
                      data-time={time}
                      className={`border border-gray-100 cursor-pointer transition-colors ${
                        isSelected
                          ? 'bg-emerald-400 hover:bg-emerald-500'
                          : 'bg-white hover:bg-emerald-50'
                      }`}
                      style={{ minWidth: 40, height: 22 }}
                      onMouseDown={() => handleMouseDown(date, time)}
                      onMouseEnter={() => handleMouseEnter(date, time)}
                      onTouchStart={() => handleTouchStart(date, time)}
                    />
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <p className="text-xs text-gray-400">
          Click and drag to select your available times
        </p>
        <button
          onClick={handleSubmit}
          disabled={selected.size === 0 || submitting}
          className="inline-flex items-center gap-2 bg-black text-white px-5 py-2.5 rounded-lg text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-800 transition-colors w-full sm:w-auto justify-center"
        >
          {submitting ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Check className="w-4 h-4" />
          )}
          Submit Availability
        </button>
      </div>
    </div>
  );
}

// -- Main Component --

export default function SchedulePageClient({ token }: { token: string }) {
  const [state, setState] = useState<PageState>('loading');
  const [data, setData] = useState<SchedulingLinkData | null>(null);
  const [error, setError] = useState<string>('');
  const [selectedSlot, setSelectedSlot] = useState<{
    start: Date;
    end: Date;
  } | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API_BASE}/api/v1/schedule/${token}`);
        if (res.status === 404) {
          setState('not_found');
          return;
        }
        if (res.status === 410) {
          setState('expired');
          return;
        }
        if (!res.ok) {
          setState('error');
          setError('Failed to load scheduling link');
          return;
        }
        const json = await res.json();
        setData(json);
        if (json.status === 'confirmed') {
          setState('already_confirmed');
        } else if (json.status === 'submitted') {
          setState('already_submitted');
        } else {
          setState('selecting');
        }
      } catch {
        setState('error');
        setError('Failed to load scheduling link');
      }
    }
    load();
  }, [token]);

  const handleConfirm = async () => {
    if (!selectedSlot) return;
    setState('confirming');
    try {
      const res = await fetch(`${API_BASE}/api/v1/schedule/${token}/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start: selectedSlot.start.toISOString(),
          end: selectedSlot.end.toISOString(),
        }),
      });
      if (res.status === 409) {
        setError('This time slot is no longer available. Please select another time.');
        setState('selecting');
        setSelectedSlot(null);
        return;
      }
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail || 'Failed to confirm time');
        setState('selecting');
        setSelectedSlot(null);
        return;
      }
      setState('success');
    } catch {
      setError('Failed to confirm time. Please try again.');
      setState('selecting');
      setSelectedSlot(null);
    }
  };

  const handleAvailabilitySubmit = async (
    availability: { date: string; start: string; end: string }[],
  ) => {
    setState('confirming');
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/schedule/${token}/availability`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ availability }),
        },
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail || 'Failed to submit availability');
        setState('selecting');
        return;
      }
      setState('submitted');
    } catch {
      setError('Failed to submit availability. Please try again.');
      setState('selecting');
    }
  };

  // -- Render --

  return (
    <div className="min-h-screen bg-white font-[family-name:var(--font-geist-sans)]">
      {/* Header */}
      <header className="border-b border-gray-100">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center gap-2">
          <a
            href="https://tryscheduled.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xl font-bold text-gray-900 font-[family-name:var(--font-space-grotesk)] tracking-tight hover:text-gray-700 transition-colors"
          >
            Scheduled
          </a>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 py-8 sm:py-12">
        <div className="flex flex-col lg:flex-row gap-8">
          {/* Left panel */}
          <div className="flex-1 min-w-0">
            {state === 'loading' && (
              <div className="flex items-center justify-center py-20 sm:py-24">
                <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
              </div>
            )}

            {state === 'not_found' && (
              <div className="text-center py-20 sm:py-24 px-4">
                <AlertCircle className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <h2 className="text-xl font-semibold text-gray-800 mb-2">
                  Link not found
                </h2>
                <p className="text-gray-500">
                  This scheduling link doesn&apos;t exist or has been removed.
                </p>
              </div>
            )}

            {state === 'expired' && (
              <div className="text-center py-20 sm:py-24 px-4">
                <Clock className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <h2 className="text-xl font-semibold text-gray-800 mb-2">
                  Link expired
                </h2>
                <p className="text-gray-500">
                  This scheduling link has expired. Please ask{' '}
                  {data?.host_name || 'the host'} for updated times.
                </p>
              </div>
            )}

            {state === 'already_confirmed' && data && (
              <div className="text-center py-20 sm:py-24 px-4">
                <Check className="w-12 h-12 text-emerald-500 mx-auto mb-4" />
                <h2 className="text-xl font-semibold text-gray-800 mb-2">
                  Already scheduled
                </h2>
                <p className="text-gray-500">
                  This meeting has already been confirmed
                  {data.confirmed_time_start &&
                    ` for ${new Date(data.confirmed_time_start).toLocaleDateString(undefined, {
                      weekday: 'long',
                      month: 'long',
                      day: 'numeric',
                    })} at ${new Date(data.confirmed_time_start).toLocaleTimeString(undefined, {
                      hour: 'numeric',
                      minute: '2-digit',
                    })}`}
                  .
                </p>
              </div>
            )}

            {state === 'already_submitted' && (
              <div className="text-center py-20 sm:py-24 px-4">
                <Check className="w-12 h-12 text-blue-500 mx-auto mb-4" />
                <h2 className="text-xl font-semibold text-gray-800 mb-2">
                  Availability received
                </h2>
                <p className="text-gray-500">
                  {data?.host_name || 'The host'} will follow up with a
                  confirmed time shortly.
                </p>
              </div>
            )}

            {state === 'success' && data && (
              <div className="text-center py-20 sm:py-24 px-4">
                <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Check className="w-8 h-8 text-emerald-600" />
                </div>
                <h2 className="text-xl font-semibold text-gray-800 mb-2">
                  You&apos;re all set!
                </h2>
                <p className="text-gray-500">
                  A calendar invite has been sent to you and {data.host_name}.
                </p>
                {selectedSlot && (
                  <p className="text-sm text-gray-400 mt-2">
                    {selectedSlot.start.toLocaleDateString(undefined, {
                      weekday: 'long',
                      month: 'long',
                      day: 'numeric',
                    })}{' '}
                    at {formatTime(selectedSlot.start)} &ndash;{' '}
                    {formatTime(selectedSlot.end)}
                  </p>
                )}
              </div>
            )}

            {state === 'submitted' && data && (
              <div className="text-center py-20 sm:py-24 px-4">
                <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Check className="w-8 h-8 text-blue-600" />
                </div>
                <h2 className="text-xl font-semibold text-gray-800 mb-2">
                  Availability submitted!
                </h2>
                <p className="text-gray-500">
                  {data.host_name} will follow up with a confirmed time shortly.
                </p>
              </div>
            )}

            {state === 'error' && (
              <div className="text-center py-20 sm:py-24 px-4">
                <AlertCircle className="w-12 h-12 text-red-300 mx-auto mb-4" />
                <h2 className="text-xl font-semibold text-gray-800 mb-2">
                  Something went wrong
                </h2>
                <p className="text-gray-500">{error}</p>
              </div>
            )}

            {(state === 'selecting' || state === 'confirming') && data && (
              <div>
                {/* Meeting info header */}
                <div className="mb-8">
                  {data.attendee_name && (
                    <p className="text-sm text-gray-500 mb-1">
                      Hi {data.attendee_name},
                    </p>
                  )}
                  <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 font-[family-name:var(--font-space-grotesk)] mb-1">
                    {data.host_name}
                  </h1>
                  <h2 className="text-base sm:text-lg text-gray-600 mb-3">
                    {data.event_summary}
                  </h2>
                  <div className="flex flex-wrap items-center gap-3 sm:gap-4 text-sm text-gray-400">
                    <span className="inline-flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" />
                      {data.duration_minutes} min
                    </span>
                    {data.location && (
                      <span className="inline-flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5" />
                        {data.location}
                      </span>
                    )}
                    {data.add_google_meet && (
                      <span className="text-blue-500">Google Meet</span>
                    )}
                  </div>
                </div>

                {error && (
                  <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    {error}
                  </div>
                )}

                {data.mode === 'suggested' ? (
                  /* -- Suggested Mode: Calendar + Time Slot Picker -- */
                  <CalendarPicker
                    windows={data.suggested_windows}
                    durationMinutes={data.duration_minutes}
                    hostName={data.host_name}
                    selectedSlot={selectedSlot}
                    onSelectSlot={(slot) => {
                      setSelectedSlot(slot);
                      setError('');
                    }}
                    onConfirm={handleConfirm}
                    confirming={state === 'confirming'}
                  />
                ) : (
                  /* -- Availability Mode: When2Meet Grid -- */
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-4">
                      Select times that work for you
                    </h3>
                    <AvailabilityGrid
                      onSubmit={handleAvailabilitySubmit}
                      submitting={state === 'confirming'}
                    />
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right panel — marketing */}
          <div className="lg:w-80 flex-shrink-0">
            <MarketingPanel />
          </div>
        </div>

        {/* Footer */}
        <div className="mt-12 pt-6 border-t border-gray-100 text-center">
          <p className="text-xs text-gray-400">
            Powered by{' '}
            <a
              href="https://tryscheduled.com"
              className="text-gray-500 hover:text-gray-700 underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              Scheduled
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
