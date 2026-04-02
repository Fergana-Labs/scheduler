'use client';

import { Brain, Mail, Calendar, Shield } from 'lucide-react';

const features = [
  {
    name: 'Knows Your Calendar',
    description:
      'Scheduled reads your availability in real-time across all your calendars. Primary calendar, shared team calendars, and even a dedicated calendar for commitments. No double-bookings, ever.',
    icon: Calendar,
    visualType: 'calendar' as const,
  },
  {
    name: 'Learns Your Preferences',
    description:
      'Scheduled analyzes how you schedule — when you like to meet, how long your meetings run, and how you communicate. Every interaction sounds like you, not a robot.',
    icon: Brain,
    visualType: 'style' as const,
  },
  {
    name: 'Handles the Back-and-Forth',
    description:
      'Not every email is a scheduling request. Scheduled uses AI to detect scheduling intent, proposes times that work, and handles the entire conversation — so you never have to.',
    icon: Mail,
    visualType: 'intent' as const,
  },
];

function StyleVisual() {
  return (
    <div className="relative space-y-3">
      <div className="rounded-lg border border-gray-100 bg-white p-3">
        <div className="mb-2 text-xs font-medium text-gray-400">Your style guide</div>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-[#43614a]" />
            <div className="text-xs text-gray-500">Casual, friendly tone</div>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-[#43614a]" />
            <div className="text-xs text-gray-500">Proposes 2-3 time slots</div>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-[#43614a]" />
            <div className="text-xs text-gray-500">Suggests specific locations</div>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-[#43614a]" />
            <div className="text-xs text-gray-500">Signs off with first name</div>
          </div>
        </div>
      </div>
      <div className="absolute -top-4 -right-4 rounded-full bg-[#43614a] p-2 shadow-md">
        <Brain className="h-5 w-5 text-white" />
      </div>
    </div>
  );
}

function IntentVisual() {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 p-3">
        <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-green-500 text-xs font-bold text-white">✓</span>
        <div className="flex-1">
          <div className="text-xs font-medium text-green-800">Requesting Meeting</div>
          <div className="text-xs text-green-600">&quot;Can we grab coffee this week?&quot;</div>
        </div>
      </div>
      <div className="flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 p-3">
        <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-blue-500 text-xs font-bold text-white">✓</span>
        <div className="flex-1">
          <div className="text-xs font-medium text-blue-800">Proposing Times</div>
          <div className="text-xs text-blue-600">&quot;How about Tuesday at 3pm?&quot;</div>
        </div>
      </div>
      <div className="flex items-center gap-3 rounded-lg border border-purple-200 bg-purple-50 p-3">
        <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-purple-500 text-xs font-bold text-white">✓</span>
        <div className="flex-1">
          <div className="text-xs font-medium text-purple-800">Confirming Time</div>
          <div className="text-xs text-purple-600">&quot;Tuesday works! See you then.&quot;</div>
        </div>
      </div>
      <div className="flex items-center gap-3 rounded-lg border border-gray-100 bg-white p-3 opacity-50">
        <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-gray-300 text-xs font-bold text-white">—</span>
        <div className="flex-1">
          <div className="text-xs font-medium text-gray-500">Not Scheduling</div>
          <div className="text-xs text-gray-400">&quot;Here&apos;s the report you asked for&quot;</div>
        </div>
      </div>
    </div>
  );
}

function CalendarVisual() {
  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-gray-100 bg-white p-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-medium text-gray-900">Thursday, Mar 19</span>
          <span className="rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">3 slots open</span>
        </div>
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 rounded bg-red-50 px-2 py-1">
            <div className="h-1.5 w-1.5 rounded-full bg-red-400" />
            <span className="text-xs text-red-600">9:00 - 10:00 Team standup</span>
          </div>
          <div className="flex items-center gap-2 rounded bg-green-50 px-2 py-1">
            <div className="h-1.5 w-1.5 rounded-full bg-green-400" />
            <span className="text-xs text-green-600">10:00 - 12:00 Available</span>
          </div>
          <div className="flex items-center gap-2 rounded bg-red-50 px-2 py-1">
            <div className="h-1.5 w-1.5 rounded-full bg-red-400" />
            <span className="text-xs text-red-600">12:00 - 1:00 Lunch</span>
          </div>
          <div className="flex items-center gap-2 rounded bg-green-50 px-2 py-1">
            <div className="h-1.5 w-1.5 rounded-full bg-green-400" />
            <span className="text-xs text-green-600">1:00 - 3:00 Available</span>
          </div>
          <div className="flex items-center gap-2 rounded bg-red-50 px-2 py-1">
            <div className="h-1.5 w-1.5 rounded-full bg-red-400" />
            <span className="text-xs text-red-600">3:00 - 4:00 Design review</span>
          </div>
          <div className="flex items-center gap-2 rounded bg-green-50 px-2 py-1">
            <div className="h-1.5 w-1.5 rounded-full bg-green-400" />
            <span className="text-xs text-green-600">4:00 - 5:00 Available</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Features() {
  return (
    <section className="bg-white py-28 sm:py-32" id="features">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="mb-6 text-center">
          <span className="inline-block rounded-full border border-gray-200 bg-[#FAFAFA] px-4 py-1.5 text-sm font-medium text-gray-600">
            Features
          </span>
        </div>
        <div className="mb-20 text-center sm:mb-24">
          <h2 className="font-[family-name:var(--font-space-grotesk)] text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
            An Assistant That Knows You
          </h2>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-gray-500">
            Scheduled understands your calendar, your preferences, and your communication style — and gets better every day
          </p>
        </div>

        {/* Features - Alternating Layout */}
        <div className="space-y-24 sm:space-y-32">
          {features.map((feature, index) => {
            const Icon = feature.icon;
            const isEven = index % 2 === 0;

            return (
              <div
                key={feature.name}
                className="grid grid-cols-1 items-center gap-12 lg:grid-cols-2 lg:gap-20"
              >
                {/* Content */}
                <div className={!isEven ? 'lg:order-2' : ''}>
                  <div className="mb-5 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gray-900">
                    <Icon className="h-7 w-7 text-white" />
                  </div>

                  <h3 className="mb-4 text-3xl font-bold tracking-tight text-gray-900">
                    {feature.name}
                  </h3>
                  <p className="max-w-lg text-lg leading-relaxed text-gray-500">
                    {feature.description}
                  </p>
                </div>

                {/* Visual */}
                <div className={!isEven ? 'lg:order-1' : ''}>
                  <div className="relative rounded-2xl border border-gray-200 bg-[#FAFAFA] p-10 sm:p-12">
                    {feature.visualType === 'style' && <StyleVisual />}
                    {feature.visualType === 'intent' && <IntentVisual />}
                    {feature.visualType === 'calendar' && <CalendarVisual />}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
