'use client';

import { useState, useEffect, useRef } from 'react';
import { ArrowRight, CalendarDays } from 'lucide-react';
import ChatPhase from './ChatPhase';
import SidePanel from './SidePanel';
import type { SidePanelStep } from './SidePanel';
import { trackPageEvent } from '@/lib/analytics';

const SIGNUP_URL = `${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/login?signup=1`;
const BOOKING_URL = process.env.NEXT_PUBLIC_DEMO_BOOKING_URL || 'mailto:henry@ferganalabs.com';

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
}

export default function DemoPage() {
  const [sidePanelStep, setSidePanelStep] = useState<SidePanelStep>('idle');
  const [demoData, setDemoData] = useState<DemoData>({});
  const [isComplete, setIsComplete] = useState(false);
  const ctaRef = useRef<HTMLDivElement>(null);
  const sidePanelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    trackPageEvent('demo_page_view');
  }, []);

  const handleSendDraft = async () => {
    trackPageEvent('demo_send_clicked');
    setSidePanelStep('sent');
    await new Promise((r) => setTimeout(r, 1200));
    setSidePanelStep('complete');
    setIsComplete(true);
    setTimeout(() => {
      ctaRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 600);
  };

  const handleStep = (
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
              <ChatPhase onStep={handleStep} isComplete={isComplete} />
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
                draftText={demoData.lastReply}
                onSendDraft={handleSendDraft}
              />
            </div>
          </div>
        </div>

        {/* Booking CTA — appears after complete */}
        {isComplete && (
          <div
            ref={ctaRef}
            className="mx-auto mt-16 max-w-2xl text-center transition-all duration-500"
          >
            <h2 className="font-[family-name:var(--font-playfair)] text-3xl font-normal italic tracking-tight text-gray-900 sm:text-4xl">
              That&apos;s Scheduled in action.
            </h2>
            <p className="mx-auto mt-3 max-w-md text-base leading-relaxed text-gray-500">
              Want to see it handle your inbox?
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row sm:gap-4">
              <a
                href={SIGNUP_URL}
                onClick={() => trackPageEvent('demo_cta_signup_click')}
                className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-full bg-[#43614a] px-7 py-3 text-sm font-medium text-white transition-all hover:bg-[#527559]"
              >
                Get Started
                <ArrowRight className="h-4 w-4" />
              </a>
              <a
                href={BOOKING_URL}
                onClick={() => trackPageEvent('demo_cta_book_click')}
                className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-full border border-gray-300 px-7 py-3 text-sm font-medium text-gray-700 transition-all hover:border-gray-900 hover:text-gray-900"
              >
                <CalendarDays className="h-4 w-4" />
                Book a Demo Call
              </a>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
