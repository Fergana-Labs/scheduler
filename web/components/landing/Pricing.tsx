'use client';

import { useState } from 'react';
import { Check, ArrowRight } from 'lucide-react';
import { sendGAEvent } from '@next/third-parties/google';
import { trackPageEvent } from '@/lib/analytics';

const features = [
  'AI scheduling assistant that knows your calendar',
  'Learns your preferences and communication style',
  'Unlimited scheduling conversations',
  'Works with any email thread',
  'Multi-calendar support',
  'Cancel anytime',
];

export default function Pricing() {
  const [plan, setPlan] = useState<'monthly' | 'annual'>('annual');

  return (
    <section className="bg-white px-4 py-20 sm:px-6 sm:py-28" id="pricing">
      <div className="mx-auto max-w-lg text-center">
        <h2 className="font-[family-name:var(--font-playfair)] text-3xl font-normal italic tracking-tight text-gray-900 sm:text-4xl">
          Simple pricing
        </h2>
        <p className="mt-4 text-base text-gray-500 sm:text-lg">
          One plan. Everything included. Try it free for 7 days.
        </p>

        {/* Plan toggle */}
        <div className="mx-auto mt-8 flex max-w-xs items-center justify-center rounded-lg bg-gray-100 p-1">
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

        <div className="mt-6 rounded-2xl border border-gray-200 bg-[#FAFAFA] p-8 sm:p-10">
          {plan === 'monthly' ? (
            <div className="flex items-baseline justify-center gap-1">
              <span className="text-5xl font-bold text-gray-900">$10</span>
              <span className="text-lg text-gray-500">/month</span>
            </div>
          ) : (
            <div>
              <div className="flex items-baseline justify-center gap-1">
                <span className="text-5xl font-bold text-gray-900">$100</span>
                <span className="text-lg text-gray-500">/year</span>
              </div>
              <p className="mt-1 text-sm text-gray-400">
                <span className="line-through">$120/yr</span> &middot; $8.33/mo
              </p>
            </div>
          )}
          <p className="mt-2 text-sm font-medium text-[#43614a]">7-day free trial</p>

          <ul className="mt-8 space-y-3 text-left">
            {features.map((feature) => (
              <li key={feature} className="flex items-start gap-3 text-sm text-gray-600">
                <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#43614a]" />
                {feature}
              </li>
            ))}
          </ul>

          <a
            href={`${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/login?signup=1`}
            onClick={() => {
              sendGAEvent('event', 'signup_click', { event_category: 'engagement', event_label: 'pricing_cta' });
              trackPageEvent('signup_click');
            }}
            className="mt-8 inline-flex w-full min-h-[44px] items-center justify-center gap-2 rounded-full bg-[#43614a] px-7 py-3.5 text-base font-medium text-white transition-all hover:bg-[#527559]"
          >
            Start Free Trial
            <ArrowRight className="h-4 w-4" />
          </a>

          <p className="mt-3 text-xs text-gray-400">
            No charge during your 7-day trial. Cancel anytime.
          </p>
        </div>
      </div>
    </section>
  );
}
