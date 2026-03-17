'use client';

import { Mail, Shield, Calendar, Brain, Check } from 'lucide-react';

const stats = [
  {
    label: 'Emails Processed',
    value: '100s',
    suffix: 'per day',
    description: 'Monitors your inbox in real-time',
    icon: Mail,
  },
  {
    label: 'Data Stored',
    value: '0',
    suffix: 'copies',
    description: 'We don’t store your email or calendar content — it stays in Gmail',
    icon: Shield,
  },
  {
    label: 'Calendar Sources',
    value: 'All',
    suffix: 'synced',
    description: 'Primary, shared, and custom calendars',
    icon: Calendar,
  },
  {
    label: 'Personalization',
    value: '100%',
    suffix: 'your voice',
    description: 'Learns your email style and preferences',
    icon: Brain,
  },
];

const capabilities = [
  {
    title: 'Real-Time Gmail Monitoring',
    desc: 'Push notifications detect new emails instantly via Google Pub/Sub',
  },
  {
    title: 'Intelligent Intent Classification',
    desc: 'Distinguishes scheduling requests from regular emails with high accuracy',
  },
  {
    title: 'Personalized Draft Composition',
    desc: 'Writes replies that match your exact email tone and scheduling habits',
  },
  {
    title: 'Multi-Calendar Availability',
    desc: 'Checks all your calendars to ensure proposed times are truly free',
  },
  {
    title: 'Preference-Aware Scheduling',
    desc: 'Respects your preferred meeting times, durations, and locations',
  },
  {
    title: 'Full Thread Context',
    desc: 'Reads the entire email thread to understand the conversation history',
  },
];

export default function Statistics() {
  return (
    <section className="bg-[#FAFAFA] py-28 sm:py-32">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="mb-6 text-center">
          <span className="inline-block rounded-full border border-gray-200 bg-white px-4 py-1.5 text-sm font-medium text-gray-600">
            By the Numbers
          </span>
        </div>
        <div className="mb-16 text-center">
          <h2 className="font-[family-name:var(--font-space-grotesk)] text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
            Scheduler by the Numbers
          </h2>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-gray-500">
            Measurable impact on your scheduling workflow without compromising privacy.
          </p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((stat, index) => {
            const Icon = stat.icon;
            return (
              <div
                key={index}
                className="relative overflow-hidden rounded-2xl border border-gray-200 bg-white p-7"
              >
                <div className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-xl bg-gray-900">
                  <Icon className="h-5 w-5 text-white" />
                </div>

                <div className="mb-1">
                  <span className="text-4xl font-bold tracking-tight text-gray-900">
                    {stat.value}
                  </span>
                  <span className="ml-1.5 text-lg font-medium text-gray-500">
                    {stat.suffix}
                  </span>
                </div>

                <div className="mb-1 text-xs font-semibold tracking-wide text-gray-400 uppercase">
                  {stat.label}
                </div>

                <p className="text-sm text-gray-500">{stat.description}</p>
              </div>
            );
          })}
        </div>

        {/* Key Capabilities */}
        <div className="mt-12 rounded-2xl border border-gray-200 bg-white p-8">
          <h3 className="mb-5 text-xl font-semibold text-gray-900">
            Key Capabilities
          </h3>
          <ul className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {capabilities.map((cap, i) => (
              <li key={i} className="flex items-start gap-3">
                <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-green-50">
                  <Check className="h-3 w-3 text-[#43614a]" />
                </span>
                <span className="text-sm text-gray-600">
                  <strong className="text-gray-900">{cap.title}:</strong>{' '}
                  {cap.desc}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
