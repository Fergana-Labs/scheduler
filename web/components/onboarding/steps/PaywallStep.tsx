'use client';

import { useState } from 'react';
import { Check, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';

interface PaywallStepProps {
  email: string;
}

export default function PaywallStep({ email }: PaywallStepProps) {
  const [plan, setPlan] = useState<'monthly' | 'annual'>('annual');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleStartTrial() {
    setLoading(true);
    setError(null);
    try {
      const res = await api<{ checkout_url: string }>('/web/api/v1/billing/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan }),
      });
      window.location.href = res.checkout_url;
    } catch {
      setError('Something went wrong. Please try again.');
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="text-xl font-semibold text-gray-900">
        You&apos;re all set up!
      </h1>
      <p className="mt-2 text-sm text-gray-500">
        Start your free trial to activate Scheduled for <span className="font-medium text-gray-700">{email}</span>.
      </p>

      {/* Plan toggle */}
      <div className="mt-6 flex items-center justify-center rounded-lg bg-gray-100 p-1">
        <button
          onClick={() => setPlan('monthly')}
          className={`flex-1 cursor-pointer rounded-md px-4 py-2 text-sm font-medium transition-colors ${
            plan === 'monthly'
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          Monthly
        </button>
        <button
          onClick={() => setPlan('annual')}
          className={`flex-1 cursor-pointer rounded-md px-4 py-2 text-sm font-medium transition-colors ${
            plan === 'annual'
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          Annual
          <span className="ml-1.5 text-xs font-semibold text-[#43614a]">Save 17%</span>
        </button>
      </div>

      <div className="mt-4 rounded-xl border border-gray-200 bg-white p-6">
        <div className="text-center">
          <p className="text-sm font-medium text-gray-500">Scheduled</p>
          {plan === 'monthly' ? (
            <div className="mt-2 flex items-baseline justify-center gap-1">
              <span className="text-4xl font-bold text-gray-900">$10</span>
              <span className="text-sm text-gray-500">/month</span>
            </div>
          ) : (
            <div className="mt-2">
              <div className="flex items-baseline justify-center gap-1">
                <span className="text-4xl font-bold text-gray-900">$100</span>
                <span className="text-sm text-gray-500">/year</span>
              </div>
              <p className="mt-0.5 text-xs text-gray-400">
                <span className="line-through">$120/yr</span> &middot; $8.33/mo
              </p>
            </div>
          )}
          <p className="mt-1 text-sm font-medium text-[#43614a]">7-day free trial</p>
        </div>

        <ul className="mt-6 space-y-2.5">
          {[
            'AI scheduling assistant that knows your calendar',
            'Learns your preferences and communication style',
            'Handles unlimited scheduling conversations',
            'Works with any email thread',
            'Cancel anytime',
          ].map((feature) => (
            <li key={feature} className="flex items-start gap-2.5 text-sm text-gray-600">
              <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#43614a]" />
              {feature}
            </li>
          ))}
        </ul>

        {error && (
          <p className="mt-4 text-center text-sm text-red-600">{error}</p>
        )}

        <button
          onClick={handleStartTrial}
          disabled={loading}
          className="mt-6 inline-flex w-full cursor-pointer items-center justify-center rounded-xl bg-[#43614a] px-6 py-4 text-base font-semibold text-white transition-colors hover:bg-[#527559] disabled:opacity-60"
        >
          {loading ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            'Start Free Trial'
          )}
        </button>

        <p className="mt-3 text-center text-xs text-gray-400">
          You won&apos;t be charged during your 7-day trial. Cancel anytime.
        </p>
      </div>
    </div>
  );
}
