'use client';

import { ArrowRight, Mail, MailOpen, Inbox, Send, Reply, Forward, Calendar, Clock, Bell, CalendarCheck, CalendarDays, Timer, Video, Users } from 'lucide-react';

// Email-related icons for the upper ribbon
const upperIcons = [Mail, MailOpen, Inbox, Send, Reply, Forward, Mail, Send, MailOpen, Inbox, Reply, Forward];
// Integration/calendar icons for the lower ribbon
const lowerIcons = [Calendar, Clock, Bell, CalendarCheck, CalendarDays, Timer, Video, Users, Calendar, Clock, Bell, CalendarCheck];

function ScrollingIconStrip({
  icons,
  direction,
  duration,
  yPosition,
  opacity,
  rotation,
}: {
  icons: typeof upperIcons;
  direction: 'left' | 'right';
  duration: number;
  yPosition: string;
  opacity: number;
  rotation: number;
}) {
  const iconSet = [...icons, ...icons]; // duplicate for seamless loop
  const animClass = direction === 'left' ? 'animate-scroll-left' : 'animate-scroll-right';

  return (
    <div
      className="absolute left-0 right-0 overflow-hidden"
      style={{ top: yPosition, transform: `rotate(${rotation}deg)`, opacity }}
    >
      <div className={`flex w-max gap-12 ${animClass}`} style={{ animationDuration: `${duration}s` }}>
        {iconSet.map((Icon, i) => (
          <div key={i} className="flex h-10 w-10 flex-shrink-0 items-center justify-center">
            <Icon className="h-7 w-7 text-gray-900" strokeWidth={1.2} />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Hero() {
  return (
    <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6">
      {/* Scrolling icon ribbons - behind content */}
      <div className="pointer-events-none absolute inset-0">
        <ScrollingIconStrip
          icons={upperIcons}
          direction="left"
          duration={30}
          yPosition="14%"
          opacity={0.15}
          rotation={-3}
        />
        <ScrollingIconStrip
          icons={lowerIcons}
          direction="right"
          duration={35}
          yPosition="78%"
          opacity={0.13}
          rotation={2}
        />
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
