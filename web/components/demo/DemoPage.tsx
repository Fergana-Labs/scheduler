'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { ArrowRight, CalendarDays, Loader2, Check, CalendarCheck } from 'lucide-react';
import ChatPhase from './ChatPhase';
import type { DemoResponse } from './ChatPhase';
import SidePanel from './SidePanel';
import type { SidePanelStep } from './SidePanel';
import { trackPageEvent } from '@/lib/analytics';

const API_BASE = process.env.NEXT_PUBLIC_CONTROL_PLANE_URL;
const SIGNUP_URL = `${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/login?signup=1`;

interface DemoData {
  events?: { start: string; end: string; summary: string }[];
  reasoning?: {
    summary: string;
    date_label: string;
    event_summary: string;
    agreed_time_start: string;
    agreed_time_end: string;
  };
  lastReply?: string;
  isConversationComplete?: boolean;
}

export default function DemoPage() {
  const [sidePanelStep, setSidePanelStep] = useState<SidePanelStep>('idle');
  const [demoData, setDemoData] = useState<DemoData>({});
  const [isComplete, setIsComplete] = useState(false);
  const [draftSent, setDraftSent] = useState(false);
  const [latestResponse, setLatestResponse] = useState<DemoResponse | null>(null);

  // Booking state
  const [showBooking, setShowBooking] = useState(false);
  const [bookingEmail, setBookingEmail] = useState('');
  const [bookingState, setBookingState] = useState<'idle' | 'loading' | 'done'>('idle');

  const ctaRef = useRef<HTMLDivElement>(null);
  const sidePanelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    trackPageEvent('demo_page_view');
  }, []);

  const handleSendDraft = useCallback(() => {
    trackPageEvent('demo_send_clicked');
    setDraftSent(true);
    setSidePanelStep('sent');

    // If the conversation is complete (time agreed), advance to invite
    if (latestResponse?.is_complete) {
      setTimeout(() => {
        setSidePanelStep('complete');
        setIsComplete(true);
        setShowBooking(true);
        setTimeout(() => {
          ctaRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 400);
      }, 1200);
    } else {
      // Not complete yet — show "sent", then let user continue
      setTimeout(() => {
        setDraftSent(false); // Reset so next round works
        // Keep showing 'sent' state — it'll reset to 'received' when user sends next message
      }, 600);
    }
  }, [latestResponse]);

  const handleDraftReady = useCallback((data: DemoResponse) => {
    setLatestResponse(data);
    setDraftSent(false);
    if (data.is_complete) {
      setDemoData((prev) => ({ ...prev, isConversationComplete: true }));
    }
  }, []);

  const handleStep = useCallback(
    (
      step: SidePanelStep,
      data?: {
        reply?: string;
        is_complete?: boolean;
        events?: { start: string; end: string; summary: string }[];
        reasoning?: DemoData['reasoning'];
      },
    ) => {
      setSidePanelStep(step);

      if (data?.events) setDemoData((prev) => ({ ...prev, events: data.events }));
      if (data?.reasoning) setDemoData((prev) => ({ ...prev, reasoning: data.reasoning }));
      if (data?.reply) setDemoData((prev) => ({ ...prev, lastReply: data.reply }));

      // On mobile, scroll side panel into view when it updates
      if (step !== 'idle' && typeof window !== 'undefined' && window.innerWidth < 1024) {
        setTimeout(() => {
          sidePanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 200);
      }
    },
    [],
  );

  const handleBook = async () => {
    if (!bookingEmail.trim() || !demoData.reasoning) return;
    setBookingState('loading');
    trackPageEvent('demo_book_clicked');

    try {
      const res = await fetch(`${API_BASE}/api/v1/demo/book`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          attendee_email: bookingEmail.trim(),
          event_summary: demoData.reasoning.event_summary,
          agreed_time_start: demoData.reasoning.agreed_time_start,
          agreed_time_end: demoData.reasoning.agreed_time_end,
        }),
      });

      if (!res.ok) throw new Error('Booking failed');
      setBookingState('done');
    } catch {
      setBookingState('idle');
    }
  };

  return (
    <div className="min-h-screen bg-[#F5F0E8]">
      {/* Header */}
      <header className="px-4 py-5 sm:px-6">
        <nav className="mx-auto flex max-w-7xl items-center justify-between">
          <a href="/" className="transition-opacity hover:opacity-70">
            <img src="/scheduled_logo.svg" alt="Scheduled" className="h-5" />
          </a>
          <span className="rounded-full border border-[#43614a]/20 px-3 py-1 text-xs font-medium text-[#43614a]">
            Interactive Demo
          </span>
        </nav>
      </header>

      <main className="px-4 pb-20 pt-4 sm:px-6 sm:pt-8">
        {/* Title */}
        <div className="mx-auto mb-8 max-w-3xl text-center lg:mb-10">
          <h1 className="font-[family-name:var(--font-playfair)] text-3xl font-normal italic tracking-tight text-gray-900 sm:text-4xl">
            Try scheduling with Sam
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-gray-500">
            Send a message like you&apos;re trying to schedule a meeting.
            Watch how Scheduled handles it behind the scenes.
          </p>
        </div>

        {/* Dual-pane layout */}
        <div className="mx-auto max-w-5xl">
          <div className="flex flex-col gap-6 lg:flex-row lg:gap-8">
            {/* Left: Email thread */}
            <div className="min-h-[500px] flex-1 lg:min-h-[600px]">
              <ChatPhase
                onStep={handleStep}
                onDraftReady={handleDraftReady}
                draftSent={draftSent}
                isComplete={isComplete}
              />
            </div>

            {/* Right: Side panel */}
            <div
              ref={sidePanelRef}
              className="w-full rounded-2xl border border-gray-200 bg-white/60 p-5 backdrop-blur-sm lg:w-[380px] lg:flex-shrink-0"
            >
              <SidePanel
                step={sidePanelStep}
                events={demoData.events}
                reasoning={demoData.reasoning}
                onSendDraft={handleSendDraft}
                isConversationComplete={demoData.isConversationComplete}
              />
            </div>
          </div>
        </div>

        {/* Booking + CTA — appears after meeting is agreed */}
        {showBooking && (
          <div
            ref={ctaRef}
            className="mx-auto mt-16 max-w-md text-center"
          >
            {/* Invite animation */}
            <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-full bg-[#43614a]/10">
              <CalendarCheck className="h-7 w-7 text-[#43614a]" />
            </div>

            <h2 className="font-[family-name:var(--font-playfair)] text-2xl font-normal italic tracking-tight text-gray-900 sm:text-3xl">
              {bookingState === 'done' ? 'You\'re booked!' : 'Meeting confirmed.'}
            </h2>

            {bookingState === 'done' ? (
              <div className="mt-4">
                <p className="text-sm text-gray-500">
                  Check your email — a calendar invite is on the way.
                </p>
                <div className="mt-8">
                  <a
                    href={SIGNUP_URL}
                    onClick={() => trackPageEvent('demo_cta_signup_click')}
                    className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-full bg-[#43614a] px-7 py-3 text-sm font-medium text-white transition-all hover:bg-[#527559]"
                  >
                    Get Scheduled for your inbox
                    <ArrowRight className="h-4 w-4" />
                  </a>
                </div>
              </div>
            ) : (
              <div className="mt-4">
                <p className="text-sm text-gray-500">
                  Want to actually book this time with Sam? Enter your email
                  and we&apos;ll send a real calendar invite.
                </p>

                <div className="mt-6 flex gap-2">
                  <input
                    type="email"
                    value={bookingEmail}
                    onChange={(e) => setBookingEmail(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleBook()}
                    placeholder="your@email.com"
                    disabled={bookingState === 'loading'}
                    className="flex-1 rounded-full border border-gray-200 bg-white px-4 py-2.5 text-sm text-gray-800 placeholder-gray-400 outline-none transition-colors focus:border-[#43614a] disabled:opacity-50"
                  />
                  <button
                    onClick={handleBook}
                    disabled={!bookingEmail.trim() || bookingState === 'loading'}
                    className="inline-flex items-center justify-center gap-1.5 rounded-full bg-[#43614a] px-5 py-2.5 text-sm font-medium text-white transition-all hover:bg-[#527559] disabled:opacity-40"
                  >
                    {bookingState === 'loading' ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <>
                        <CalendarDays className="h-4 w-4" />
                        Book it
                      </>
                    )}
                  </button>
                </div>

                <p className="mt-6 text-xs text-gray-400">
                  Or{' '}
                  <a
                    href={SIGNUP_URL}
                    onClick={() => trackPageEvent('demo_cta_signup_click')}
                    className="text-[#43614a] underline"
                  >
                    get Scheduled for your own inbox →
                  </a>
                </p>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
