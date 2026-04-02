'use client';

import { Calendar, Sparkles, MessageSquare } from 'lucide-react';

interface WelcomeStepProps {
  onContinue: () => void;
}

export default function WelcomeStep({ onContinue }: WelcomeStepProps) {
  return (
    <div>
      <h1 className="text-xl font-semibold text-gray-900">
        Let&apos;s set you up
      </h1>
      <p className="mt-2 text-sm text-gray-500">
        In just a few steps, Scheduled will learn how you work and start handling your scheduling.
      </p>

      <div className="mt-8 space-y-4">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-[#43614a]/10">
            <Calendar className="h-4.5 w-4.5 text-[#43614a]" />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-900">Knows your calendar</p>
            <p className="text-sm text-gray-500">Reads your availability in real-time so you never double-book.</p>
          </div>
        </div>

        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-[#43614a]/10">
            <Sparkles className="h-4.5 w-4.5 text-[#43614a]" />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-900">Learns your preferences</p>
            <p className="text-sm text-gray-500">Understands when and how you like to meet.</p>
          </div>
        </div>

        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-[#43614a]/10">
            <MessageSquare className="h-4.5 w-4.5 text-[#43614a]" />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-900">Handles the back-and-forth</p>
            <p className="text-sm text-gray-500">Responds to scheduling emails so you don&apos;t have to.</p>
          </div>
        </div>
      </div>

      <button
        onClick={onContinue}
        className="mt-8 inline-flex w-full cursor-pointer items-center justify-center rounded-xl bg-[#43614a] px-6 py-4 text-base font-semibold text-white transition-colors hover:bg-[#527559]"
      >
        Get Started
      </button>
    </div>
  );
}
