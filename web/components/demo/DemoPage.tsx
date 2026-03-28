'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import ChatPhase from './ChatPhase';
import type { DemoResponse } from './ChatPhase';
import SidePanel from './SidePanel';
import type { SidePanelStep } from './SidePanel';
import { trackPageEvent } from '@/lib/analytics';

export default function DemoPage() {
  const [sidePanelStep, setSidePanelStep] = useState<SidePanelStep>('idle');
  const [isComplete, setIsComplete] = useState(false);
  const [draftSent, setDraftSent] = useState(false);
  const [autopilotEnabled, setAutopilotEnabled] = useState(false);
  const [exchangeCount, setExchangeCount] = useState(0);
  const [latestResponse, setLatestResponse] = useState<DemoResponse | null>(null);

  const sidePanelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    trackPageEvent('demo_page_view');
  }, []);

  const handleSendDraft = useCallback(() => {
    trackPageEvent('demo_send_clicked');
    setDraftSent(true);
    setSidePanelStep('sent');

    const newCount = exchangeCount + 1;
    setExchangeCount(newCount);

    // Enable autopilot after first manual send
    if (newCount === 1) {
      setAutopilotEnabled(true);
    }

    if (latestResponse?.is_complete) {
      setTimeout(() => {
        setSidePanelStep('complete');
        setIsComplete(true);
      }, 1200);
    } else {
      setTimeout(() => {
        setDraftSent(false);
      }, 600);
    }
  }, [latestResponse, exchangeCount]);

  const handleDraftReady = useCallback((data: DemoResponse) => {
    setLatestResponse(data);
    setDraftSent(false);
  }, []);

  const handleStep = useCallback(
    (
      step: SidePanelStep,
      data?: Partial<DemoResponse>,
    ) => {
      setSidePanelStep(step);

      // Autopilot path sets complete via onStep
      if (step === 'complete') {
        setIsComplete(true);
      }

      // On mobile, scroll side panel into view
      if (step !== 'idle' && typeof window !== 'undefined' && window.innerWidth < 1024) {
        setTimeout(() => {
          sidePanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 200);
      }
    },
    [],
  );

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
        </div>

        {/* Dual-pane layout */}
        <div className="mx-auto max-w-5xl">
          <div className="flex flex-col gap-6 lg:flex-row lg:gap-8">
            {/* Left: Email thread */}
            <div className="min-h-[500px] flex-1 lg:min-h-[600px]">
              <ChatPhase
                onStep={handleStep}
                onDraftReady={handleDraftReady}
                onSendDraft={handleSendDraft}
                draftSent={draftSent}
                isComplete={isComplete}
                autopilot={autopilotEnabled}
              />
            </div>

            {/* Right: Side panel */}
            <div
              ref={sidePanelRef}
              className="w-full rounded-2xl border border-gray-200 bg-white/60 p-5 backdrop-blur-sm lg:w-[380px] lg:flex-shrink-0"
            >
              <SidePanel
                step={sidePanelStep}
                autopilot={autopilotEnabled}
              />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
