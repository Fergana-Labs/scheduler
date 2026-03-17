'use client';

import { useState, useEffect } from 'react';
import {
  Mail,
  Calendar,
  Clock,
  MessageSquare,
  Users,
  CalendarCheck,
  Sparkles,
  ArrowRight,
} from 'lucide-react';

const rotatingItems = [
  { text: 'Conflicts', icon: Calendar },
  { text: 'Invites', icon: Clock },
  { text: 'Follow-ups', icon: MessageSquare },
  { text: 'Confirmations', icon: CalendarCheck },
];

export default function Hero() {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    const interval = setInterval(() => {
      setIsVisible(false);

      setTimeout(() => {
        setCurrentIndex(prevIndex => (prevIndex + 1) % rotatingItems.length);
        setIsVisible(true);
      }, 300);
    }, 2500);

    return () => clearInterval(interval);
  }, []);

  const CurrentIcon = rotatingItems[currentIndex].icon;

  return (
    <section className="relative py-20 sm:py-28 lg:py-36">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-2 lg:gap-16">
          {/* Left Column - Text + CTA */}
          <div>
            {/* Pill Badge */}
            <div className="mb-6">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-gray-200 bg-white px-3.5 py-1.5 text-sm font-medium text-gray-700 shadow-sm">
                <Sparkles className="h-3.5 w-3.5 text-[#43614a]" />
                AI-powered scheduling agent
              </span>
            </div>

            {/* Headline */}
            <h1 className="font-[family-name:var(--font-space-grotesk)] text-5xl leading-tight font-bold tracking-tight text-gray-900 sm:text-6xl lg:text-7xl">
              Automate
              <br />
              <span className="inline-flex h-[3.5rem] sm:h-[4rem] lg:h-[4.5rem] items-center overflow-hidden">
                <span
                  className={`inline-flex items-center gap-3 whitespace-nowrap bg-gradient-to-r from-[#43614a] to-[#527559] bg-clip-text text-transparent transition-opacity duration-300 ${
                    isVisible ? 'opacity-100' : 'opacity-0'
                  }`}
                >
                  <CurrentIcon className="h-12 w-12 text-[#43614a] sm:h-14 sm:w-14 lg:h-16 lg:w-16" />
                  {rotatingItems[currentIndex].text}
                </span>
              </span>
            </h1>

            {/* Subheadline */}
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-gray-500 sm:text-xl">
              An AI agent that monitors your inbox, detects scheduling requests,
              checks your calendar, and drafts perfect replies—all in your voice.
            </p>

            {/* CTA */}
            <div className="mt-10 flex flex-col items-start gap-2">
              <a
                href={`${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/google`}
                className="inline-flex items-center gap-3 rounded-2xl bg-gray-900 px-10 py-5 text-lg font-semibold text-white shadow-lg transition-all duration-200 hover:scale-[1.02] hover:bg-gray-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-900"
              >
                Sign Up
                <ArrowRight className="h-5 w-5" />
              </a>
              <span className="text-sm text-gray-400">
                Works with Gmail and Google Calendar
              </span>
            </div>
          </div>

          {/* Right Column - Visual */}
          <div className="relative">
            <div className="absolute inset-0 -z-10 scale-105 transform rounded-3xl bg-gradient-to-r from-[#527559]/10 to-[#43614a]/10 blur-2xl" />
            <div className="rounded-2xl border border-gray-200 bg-[#FAFAFA] p-6 shadow-2xl sm:p-8">
              {/* Email Thread Visual */}
              <div className="space-y-4">
                {/* Incoming Email */}
                <div className="rounded-xl border border-gray-100 bg-white p-4">
                  <div className="mb-2 flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100">
                      <Mail className="h-4 w-4 text-blue-600" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-900">Sarah Chen</p>
                      <p className="text-xs text-gray-400">2 min ago</p>
                    </div>
                  </div>
                  <p className="text-sm text-gray-600">
                    &quot;Hey! Would love to grab coffee and chat about the partnership. Are you free this week?&quot;
                  </p>
                </div>

                {/* AI Processing */}
                <div className="flex items-center gap-3 px-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#43614a]">
                    <Sparkles className="h-4 w-4 text-white" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-[#43614a]">AI Agent</span>
                      <span className="inline-flex items-center rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">
                        Scheduling detected
                      </span>
                    </div>
                    <p className="text-xs text-gray-400">Checking calendar availability...</p>
                  </div>
                </div>

                {/* Draft Reply */}
                <div className="rounded-xl border border-[#43614a]/20 bg-green-50/50 p-4">
                  <div className="mb-2 flex items-center gap-2">
                    <span className="inline-flex items-center rounded-full bg-[#43614a] px-2 py-0.5 text-xs font-medium text-white">
                      Draft
                    </span>
                    <span className="text-xs text-gray-400">Ready to send</span>
                  </div>
                  <p className="text-sm text-gray-600">
                    &quot;Hey Sarah! That sounds great. I&apos;m free Thursday afternoon or Friday morning — does either work for you? Happy to meet at Blue Bottle on Market St.&quot;
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
