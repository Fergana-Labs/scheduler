'use client';

import { ArrowRight } from 'lucide-react';

export default function Hero() {
  return (
    <section className="relative flex min-h-screen flex-col items-center justify-center px-6">
      <div className="mx-auto max-w-4xl text-center">
        {/* Headline with mixed typography */}
        <h1 className="text-5xl leading-[1.1] tracking-tight text-gray-900 sm:text-7xl lg:text-8xl">
          <span className="font-[family-name:var(--font-playfair)] font-normal italic">
            Don&apos;t schedule,
          </span>
          <br />
          <span className="font-[family-name:var(--font-space-grotesk)] font-bold">
            just email
          </span>
        </h1>

        {/* Subtitle */}
        <p className="mx-auto mt-8 max-w-lg text-lg leading-relaxed text-gray-500 sm:text-xl">
          The AI agent that reads your inbox, checks your
          calendar, and drafts replies — in your voice.
        </p>

        {/* CTA */}
        <div className="mt-10 flex flex-col items-center gap-3">
          <a
            href={`${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/google`}
            className="inline-flex items-center gap-2 rounded-full bg-[#43614a] px-7 py-3.5 text-base font-medium text-white transition-all hover:bg-[#527559]"
          >
            Get Started
            <ArrowRight className="h-4 w-4" />
          </a>
          <span className="text-sm text-gray-400">
            Works with Gmail and Google Calendar
          </span>
        </div>
      </div>
    </section>
  );
}
