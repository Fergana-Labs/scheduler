'use client';

import { useState } from 'react';
import { ArrowLeft, Calendar, Mail, Check } from 'lucide-react';

interface ModeChoiceStepProps {
  initialMode: 'bot' | 'draft';
  onContinue: (mode: 'bot' | 'draft') => void;
  onBack: () => void;
}

export default function ModeChoiceStep({ initialMode, onContinue, onBack }: ModeChoiceStepProps) {
  const [selected, setSelected] = useState<'bot' | 'draft'>(initialMode);

  return (
    <div>
      <button
        onClick={onBack}
        className="mb-4 flex cursor-pointer items-center gap-1 text-sm text-gray-400 transition-colors hover:text-gray-600"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back
      </button>

      <h1 className="text-xl font-semibold text-gray-900">
        How should Scheduled work?
      </h1>
      <p className="mt-2 text-sm text-gray-500">
        Choose how you&apos;d like Scheduled to handle your scheduling.
      </p>

      <div className="mt-6 space-y-3">
        {/* Bot mode — recommended */}
        <button
          onClick={() => setSelected('bot')}
          className={`relative w-full cursor-pointer rounded-xl border-2 p-5 text-left transition-colors ${
            selected === 'bot'
              ? 'border-[#43614a] bg-[#43614a]/5'
              : 'border-gray-200 hover:border-gray-300'
          }`}
        >
          <div className="absolute -top-2.5 right-4 rounded-full bg-[#43614a] px-2.5 py-0.5 text-xs font-semibold text-white">
            Recommended
          </div>
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-[#43614a]/10">
              <Calendar className="h-5 w-5 text-[#43614a]" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold text-gray-900">Scheduling Assistant</p>
              <p className="mt-1 text-sm text-gray-500">
                Scheduled acts as your visible scheduling assistant — like having a human EA.
                Just CC <span className="font-medium text-gray-700">scheduling@tryscheduled.com</span> on any email thread.
              </p>
              <ul className="mt-3 space-y-1.5">
                <li className="flex items-center gap-2 text-sm text-gray-600">
                  <Check className="h-3.5 w-3.5 text-[#43614a]" />
                  Only needs calendar access
                </li>
                <li className="flex items-center gap-2 text-sm text-gray-600">
                  <Check className="h-3.5 w-3.5 text-[#43614a]" />
                  Counterparties interact with your assistant directly
                </li>
                <li className="flex items-center gap-2 text-sm text-gray-600">
                  <Check className="h-3.5 w-3.5 text-[#43614a]" />
                  No Gmail access needed — your inbox stays private
                </li>
              </ul>
            </div>
          </div>
        </button>

        {/* Draft mode */}
        <button
          onClick={() => setSelected('draft')}
          className={`w-full cursor-pointer rounded-xl border-2 p-5 text-left transition-colors ${
            selected === 'draft'
              ? 'border-[#43614a] bg-[#43614a]/5'
              : 'border-gray-200 hover:border-gray-300'
          }`}
        >
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-gray-100">
              <Mail className="h-5 w-5 text-gray-600" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold text-gray-900">Draft Suggestions</p>
              <p className="mt-1 text-sm text-gray-500">
                Scheduled reads your email and drafts scheduling replies for you to review and send.
              </p>
              <ul className="mt-3 space-y-1.5">
                <li className="flex items-center gap-2 text-sm text-gray-600">
                  <Check className="h-3.5 w-3.5 text-gray-400" />
                  Requires Gmail + Calendar access
                </li>
                <li className="flex items-center gap-2 text-sm text-gray-600">
                  <Check className="h-3.5 w-3.5 text-gray-400" />
                  You review and send every reply
                </li>
              </ul>
            </div>
          </div>
        </button>
      </div>

      <button
        onClick={() => onContinue(selected)}
        className="mt-8 inline-flex w-full cursor-pointer items-center justify-center rounded-xl bg-[#43614a] px-6 py-4 text-base font-semibold text-white transition-colors hover:bg-[#527559]"
      >
        Continue
      </button>
    </div>
  );
}
