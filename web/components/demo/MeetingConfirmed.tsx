'use client';

import { useState } from 'react';
import { CalendarCheck, Video, Loader2, ArrowRight, Check } from 'lucide-react';
import { trackPageEvent } from '@/lib/analytics';

const API_BASE = process.env.NEXT_PUBLIC_CONTROL_PLANE_URL;
const SIGNUP_URL = `${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/login?signup=1`;

interface Props {
  eventSummary: string;
  agreedTimeStart: string;
  agreedTimeEnd: string;
}

function formatDateTime(iso: string): string {
  try {
    const dt = new Date(iso);
    return dt.toLocaleString('en-US', {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return iso;
  }
}

function formatTime(iso: string): string {
  try {
    const dt = new Date(iso);
    return dt.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
  } catch {
    return iso;
  }
}

export default function MeetingConfirmed({ eventSummary, agreedTimeStart, agreedTimeEnd }: Props) {
  const [email, setEmail] = useState('');
  const [state, setState] = useState<'idle' | 'loading' | 'done'>('idle');

  const handleBook = async () => {
    if (!email.trim()) return;
    setState('loading');
    trackPageEvent('demo_book_clicked');

    try {
      const res = await fetch(`${API_BASE}/api/v1/demo/book`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          attendee_email: email.trim(),
          event_summary: eventSummary,
          agreed_time_start: agreedTimeStart,
          agreed_time_end: agreedTimeEnd,
        }),
      });
      if (!res.ok) throw new Error('Booking failed');
      setState('done');
    } catch {
      setState('idle');
    }
  };

  return (
    <div className="border-l-2 border-[#43614a] bg-[#43614a]/5 px-5 py-4">
      <div className="flex items-center gap-2">
        <CalendarCheck className="h-4 w-4 text-[#43614a]" />
        <span className="text-sm font-semibold text-gray-900">Meeting Confirmed</span>
      </div>

      <div className="mt-3 space-y-1.5 text-sm text-gray-700">
        <div>{eventSummary}</div>
        <div className="text-gray-500">
          {formatDateTime(agreedTimeStart)} – {formatTime(agreedTimeEnd)}
        </div>
        <div className="flex items-center gap-1 text-gray-500">
          <Video className="h-3.5 w-3.5" />
          Google Meet
        </div>
      </div>

      <div className="mt-4 text-xs text-gray-500">
        Scheduled verified the sent message and created a calendar invite.
      </div>

      {state === 'done' ? (
        <div className="mt-4">
          <div className="flex items-center gap-1.5 text-sm font-medium text-[#43614a]">
            <Check className="h-4 w-4" />
            You&apos;re booked! Check your email for the invite.
          </div>
          <div className="mt-4">
            <a
              href={SIGNUP_URL}
              onClick={() => trackPageEvent('demo_cta_signup_click')}
              className="inline-flex items-center gap-1.5 text-sm font-medium text-[#43614a] underline underline-offset-2"
            >
              Get Scheduled for your inbox
              <ArrowRight className="h-3.5 w-3.5" />
            </a>
          </div>
        </div>
      ) : (
        <div className="mt-4">
          <div className="text-xs text-gray-500">
            Want to actually schedule a meeting to help you get started? Enter your email and we&apos;ll send a real invite.
          </div>
          <div className="mt-2 flex gap-2">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleBook()}
              placeholder="your@email.com"
              disabled={state === 'loading'}
              className="flex-1 rounded border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 placeholder-gray-400 outline-none focus:border-[#43614a] disabled:opacity-50"
            />
            <button
              onClick={handleBook}
              disabled={!email.trim() || state === 'loading'}
              className="inline-flex items-center gap-1 rounded bg-[#43614a] px-3 py-1.5 text-sm font-medium text-white hover:bg-[#527559] disabled:opacity-40"
            >
              {state === 'loading' ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                'Book it'
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
