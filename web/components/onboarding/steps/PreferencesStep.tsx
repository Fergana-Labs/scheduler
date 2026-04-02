'use client';

import { useState } from 'react';
import { ArrowLeft, Check, Sparkles } from 'lucide-react';

const PREFERENCES = [
  'Protected times for focused work',
  'Travel often between time zones',
  'Prefer grouping meetings together',
  'Prefer buffer time between meetings',
  'Have hard stops between meetings',
  'Work often outside normal business hours',
  'Prefer no morning meetings',
  'Prefer no evening meetings',
  'In-person meetings preferred',
];

interface PreferencesStepProps {
  initialValue: string[];
  onContinue: (preferences: string[]) => void;
  onBack: () => void;
}

export default function PreferencesStep({ initialValue, onContinue, onBack }: PreferencesStepProps) {
  const [selected, setSelected] = useState<string[]>(initialValue);

  function toggle(pref: string) {
    setSelected((prev) =>
      prev.includes(pref) ? prev.filter((p) => p !== pref) : [...prev, pref]
    );
  }

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
        Your scheduling preferences
      </h1>
      <div className="mt-2 flex items-start gap-2">
        <Sparkles className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#43614a]" />
        <p className="text-sm text-gray-500">
          Select any that apply. We&apos;ll also learn these and other preferences automatically from your calendar.
        </p>
      </div>

      <div className="mt-6 space-y-2">
        {PREFERENCES.map((pref) => (
          <button
            key={pref}
            onClick={() => toggle(pref)}
            className={`flex w-full cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 text-left text-sm transition-colors ${
              selected.includes(pref)
                ? 'border-[#43614a] bg-[#43614a]/5 text-gray-900'
                : 'border-gray-200 text-gray-600 hover:border-gray-300'
            }`}
          >
            <div className={`flex h-4.5 w-4.5 flex-shrink-0 items-center justify-center rounded border ${
              selected.includes(pref)
                ? 'border-[#43614a] bg-[#43614a]'
                : 'border-gray-300'
            }`}>
              {selected.includes(pref) && <Check className="h-3 w-3 text-white" />}
            </div>
            {pref}
          </button>
        ))}
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
