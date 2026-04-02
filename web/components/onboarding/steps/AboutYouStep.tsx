'use client';

import { useState } from 'react';
import { ArrowLeft, Check } from 'lucide-react';

const ROLES = [
  'Founder / CEO',
  'Investor / VC',
  'Sales',
  'Recruiting',
  'Consultant',
  'Product Manager',
  'Engineering',
  'Executive Assistant',
  'Operations',
];

interface AboutYouStepProps {
  initialValue: string;
  onContinue: (role: string) => void;
  onBack: () => void;
}

export default function AboutYouStep({ initialValue, onContinue, onBack }: AboutYouStepProps) {
  const [selected, setSelected] = useState(initialValue);
  const [customRole, setCustomRole] = useState(
    initialValue && !ROLES.includes(initialValue) ? initialValue : ''
  );
  const isOther = selected === '__other__' || (selected && !ROLES.includes(selected));

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
        What&apos;s your role?
      </h1>
      <p className="mt-2 text-sm text-gray-500">
        This helps Scheduled understand which meetings matter most to you.
      </p>

      <div className="mt-6 flex flex-wrap gap-2">
        {ROLES.map((role) => (
          <button
            key={role}
            onClick={() => setSelected(role)}
            className={`cursor-pointer rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
              selected === role
                ? 'border-[#43614a] bg-[#43614a]/10 text-[#43614a]'
                : 'border-gray-200 text-gray-600 hover:border-gray-300'
            }`}
          >
            {selected === role && <Check className="mr-1 -ml-0.5 inline h-3.5 w-3.5" />}
            {role}
          </button>
        ))}
        <button
          onClick={() => setSelected('__other__')}
          className={`cursor-pointer rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
            isOther
              ? 'border-[#43614a] bg-[#43614a]/10 text-[#43614a]'
              : 'border-gray-200 text-gray-600 hover:border-gray-300'
          }`}
        >
          {isOther && <Check className="mr-1 -ml-0.5 inline h-3.5 w-3.5" />}
          Other
        </button>
      </div>

      {isOther && (
        <input
          type="text"
          value={customRole}
          onChange={(e) => setCustomRole(e.target.value)}
          placeholder="Your role"
          autoFocus
          className="mt-3 w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm text-gray-900 placeholder-gray-400 outline-none transition-colors focus:border-[#43614a] focus:ring-1 focus:ring-[#43614a]"
        />
      )}

      <button
        onClick={() => {
          const role = isOther ? (customRole || 'Other') : selected;
          onContinue(role);
        }}
        disabled={!selected}
        className="mt-8 inline-flex w-full cursor-pointer items-center justify-center rounded-xl bg-[#43614a] px-6 py-4 text-base font-semibold text-white transition-colors hover:bg-[#527559] disabled:cursor-default disabled:opacity-40"
      >
        Continue
      </button>
    </div>
  );
}
