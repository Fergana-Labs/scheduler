'use client';

import { ArrowRight, Mail, MailOpen, Inbox, Send, Reply, Forward, Calendar, Clock, Bell, CalendarCheck, CalendarDays, Timer, Video, Users } from 'lucide-react';

const upperIcons = [Mail, MailOpen, Inbox, Send, Reply, Forward, Mail, Send, MailOpen, Inbox, Reply, Forward, Mail, MailOpen, Send, Reply, Forward, Inbox, Mail, Send];
const lowerIcons = [Calendar, Clock, Bell, CalendarCheck, CalendarDays, Timer, Video, Users, Calendar, Clock, Bell, CalendarCheck, CalendarDays, Timer, Video, Users, Calendar, Clock, Bell, CalendarCheck];

// Asymmetric, playful curves — staying clear of the center hero area
const UPPER_PATH = "path('M -200,100 C 50,20 180,200 420,60 C 580,-30 700,150 900,80 C 1080,20 1200,160 1400,70 C 1550,10 1650,130 1750,80')";
const LOWER_PATH = "path('M -200,680 C 80,630 200,720 380,690 C 560,660 650,750 820,710 C 1000,670 1100,740 1250,700 C 1400,660 1550,730 1750,680')";

function IconStream({
  icons,
  offsetPath,
  duration,
  opacity,
  reverse,
}: {
  icons: typeof upperIcons;
  offsetPath: string;
  duration: number;
  opacity: number;
  reverse?: boolean;
}) {
  const count = icons.length;

  return (
    <>
      {icons.map((Icon, i) => {
        const delay = -(duration / count) * i;
        return (
          <div
            key={i}
            className="icon-on-path absolute left-0 top-0"
            style={{
              offsetPath,
              offsetRotate: '0deg',
              animationName: reverse ? 'move-along-path-reverse' : 'move-along-path',
              animationDuration: `${duration}s`,
              animationTimingFunction: 'linear',
              animationIterationCount: 'infinite',
              animationDelay: `${delay}s`,
              opacity,
            }}
          >
            <Icon className="h-5 w-5 text-gray-900" strokeWidth={1.3} />
          </div>
        );
      })}
    </>
  );
}

export default function Hero() {
  return (
    <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6">
      {/* Flowing icon streams - behind content */}
      <div className="pointer-events-none absolute inset-0" style={{ position: 'absolute' }}>
        <div className="relative h-full w-full" style={{ transform: 'scale(1)', transformOrigin: 'top left' }}>
          <IconStream
            icons={upperIcons}
            offsetPath={UPPER_PATH}
            duration={40}
            opacity={0.14}
          />
          <IconStream
            icons={lowerIcons}
            offsetPath={LOWER_PATH}
            duration={45}
            opacity={0.12}
            reverse
          />
        </div>
      </div>

      {/* Main content */}
      <div className="relative z-10 mx-auto max-w-4xl text-center">
        <h1 className="font-[family-name:var(--font-playfair)] text-5xl font-normal italic leading-[1.1] tracking-tight text-gray-900 sm:text-7xl lg:text-8xl">
          Just hit
          <br />
          send
        </h1>

        <p className="mx-auto mt-8 max-w-lg text-lg leading-relaxed text-gray-500 sm:text-xl">
          Scheduled is an open-source agent that lives in your email and automatically drafts responses.
        </p>

        <div className="mt-10 flex flex-col items-center gap-3">
          <a
            href={`${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/google`}
            className="inline-flex items-center gap-2 rounded-full bg-[#43614a] px-7 py-3.5 text-base font-medium text-white transition-all hover:bg-[#527559]"
          >
            Get Started
            <ArrowRight className="h-4 w-4" />
          </a>
        </div>
      </div>
    </section>
  );
}
