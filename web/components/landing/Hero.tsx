'use client';

import { useRef, useState, useEffect, useCallback } from 'react';
import { ArrowRight, Check, Mail, MailOpen, Inbox, Send, Reply, Forward, Calendar, Clock, Bell, CalendarCheck, CalendarDays, Timer, Video, Users } from 'lucide-react';

const upperIcons = [Mail, MailOpen, Inbox, Send, Reply, Forward, Mail, Send, MailOpen, Inbox, Reply, Forward, Mail, MailOpen, Send, Reply, Forward, Inbox, Mail, Send];
const lowerIcons = [Calendar, Clock, Bell, CalendarCheck, CalendarDays, Timer, Video, Users, Calendar, Clock, Bell, CalendarCheck, CalendarDays, Timer, Video, Users, Calendar, Clock, Bell, CalendarCheck];

const UPPER_PATH = "path('M -200,100 C 50,20 180,200 420,60 C 580,-30 700,150 900,80 C 1080,20 1200,160 1400,70 C 1550,10 1650,130 1750,80')";
const LOWER_PATH = "path('M -200,680 C 80,630 200,720 380,690 C 560,660 650,750 820,710 C 1000,670 1100,740 1250,700 C 1400,660 1550,730 1750,680')";

const EMAILS = [
  {
    from: 'Sarah Chen',
    subject: 'Re: Q2 Planning Session',
    preview: 'Hey, can we move our Thursday sync to Friday? I have a conflict with the board meeting...',
    draft: 'Hi Sarah, Friday works great! I\'ve moved our sync to 2pm — see you then.',
  },
  {
    from: 'James Morrison',
    subject: 'Intro: Alex from Acme Corp',
    preview: 'Wanted to connect you two — Alex is leading their API integration and I think there\'s a lot of synergy...',
    draft: 'Thanks James! Alex, great to meet you. I\'m free Wednesday or Thursday afternoon if you want to hop on a quick call.',
  },
  {
    from: 'Priya Patel',
    subject: 'Quick question about the demo',
    preview: 'Hi! Loved the demo yesterday. A few of us had questions about the pricing tiers and whether...',
    draft: 'Hi Priya, thanks so much! I\'ve attached our pricing breakdown. Happy to walk through it — does Tuesday at 11am work?',
  },
  {
    from: 'Mike Torres',
    subject: 'Lunch next week?',
    preview: 'It\'s been ages! Are you free for lunch sometime next week? I\'m around Tuesday through Thursday...',
    draft: 'Mike! Yes, way overdue. How about Wednesday at noon? There\'s a great new spot on 3rd.',
  },
  {
    from: 'Lisa Wang',
    subject: 'Re: Contract Review',
    preview: 'Our legal team flagged a couple of items in section 4. Can we set up a call to go through them...',
    draft: 'Hi Lisa, absolutely. I\'ve got time Thursday at 3pm or Friday morning — which works better for your team?',
  },
];

// How many px of scroll to dismiss each card
const SCROLL_PER_CARD = 150;

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
  const sectionRef = useRef<HTMLDivElement>(null);
  const [cardStates, setCardStates] = useState<number[]>(EMAILS.map(() => 0));

  const handleScroll = useCallback(() => {
    if (!sectionRef.current) return;

    const rect = sectionRef.current.getBoundingClientRect();
    // First pixel of scroll starts the animation
    const progress = Math.max(0, -rect.top);

    const newStates = EMAILS.map((_, i) => {
      const cardStart = i * SCROLL_PER_CARD;
      const cardEnd = cardStart + SCROLL_PER_CARD;
      if (progress <= cardStart) return 0;
      if (progress >= cardEnd) return 1;
      return (progress - cardStart) / SCROLL_PER_CARD;
    });

    setCardStates(newStates);
  }, []);

  useEffect(() => {
    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, [handleScroll]);

  // Extra height beyond the viewport to give scroll room for card animations
  const scrollRoom = EMAILS.length * SCROLL_PER_CARD + 200;

  return (
    <section
      ref={sectionRef}
      className="relative overflow-hidden px-6"
      style={{ paddingBottom: `${scrollRoom}px` }}
    >
      {/* Flowing icon streams - behind everything */}
      <div className="pointer-events-none absolute inset-0">
        <div className="relative h-full w-full" style={{ transform: 'scale(1)', transformOrigin: 'top left' }}>
          <IconStream icons={upperIcons} offsetPath={UPPER_PATH} duration={40} opacity={0.14} />
          <IconStream icons={lowerIcons} offsetPath={LOWER_PATH} duration={45} opacity={0.12} reverse />
        </div>
      </div>

      {/* Two-column hero — scrolls naturally with the page */}
      <div className="relative z-10 mx-auto flex min-h-screen w-full max-w-6xl items-center gap-12 lg:gap-20">
        {/* Left: headline + CTA */}
        <div className="flex-1">
          <h1 className="font-[family-name:var(--font-playfair)] text-5xl font-normal italic leading-[1.1] tracking-tight text-gray-900 sm:text-7xl lg:text-8xl">
            Just hit
            <br />
            send
          </h1>

          <p className="mt-8 max-w-md text-lg leading-relaxed text-gray-500 sm:text-xl">
            Scheduled is an open-source agent that lives in your email and automatically drafts responses.
          </p>

          <div className="mt-10">
            <a
              href={`${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/google`}
              className="inline-flex items-center gap-2 rounded-full bg-[#43614a] px-7 py-3.5 text-base font-medium text-white transition-all hover:bg-[#527559]"
            >
              Get Started
              <ArrowRight className="h-4 w-4" />
            </a>
          </div>
        </div>

        {/* Right: email card stack */}
        <div className="relative hidden h-[420px] w-[440px] flex-shrink-0 lg:block">
          {EMAILS.map((email, i) => {
            const progress = cardStates[i] ?? 0;
            const isGone = progress >= 1;
            const stackOffset = (EMAILS.length - 1 - i) * 4;
            const stackScale = 1 - (EMAILS.length - 1 - i) * 0.02;

            const ease = progress * progress * (3 - 2 * progress);

            const translateX = ease * 900;
            const translateY = ease * -150;
            const rotate = ease * 28;
            const opacity = 1 - ease * 0.5;
            const scale = stackScale + ease * 0.05;

            const transform = progress > 0
              ? `translate(${translateX}px, ${translateY}px) rotate(${rotate}deg) scale(${scale})`
              : `translateY(${stackOffset}px) scale(${stackScale})`;

            return (
              <div
                key={i}
                className="absolute inset-0 will-change-transform"
                style={{
                  transform,
                  opacity: isGone ? 0 : opacity,
                  zIndex: EMAILS.length - i,
                  pointerEvents: 'none',
                }}
              >
                <div className="h-full w-full rounded-2xl border border-gray-200 bg-white p-6 shadow-lg">
                  <div className="mb-4 flex items-start justify-between">
                    <div>
                      <div className="text-sm font-semibold text-gray-900">{email.from}</div>
                      <div className="text-sm font-medium text-gray-700">{email.subject}</div>
                    </div>
                    <div className="text-xs text-gray-400">2m ago</div>
                  </div>

                  <div className="mb-5 rounded-lg bg-gray-50 px-4 py-3 text-sm leading-relaxed text-gray-600">
                    {email.preview}
                  </div>

                  <div className="mb-4 flex items-center gap-3">
                    <div className="h-px flex-1 bg-gray-200" />
                    <span className="text-xs font-medium tracking-wide text-[#43614a]">
                      DRAFT RESPONSE
                    </span>
                    <div className="h-px flex-1 bg-gray-200" />
                  </div>

                  <div className="text-sm leading-relaxed text-gray-800">
                    {email.draft}
                  </div>
                </div>

                {/* Sent badge */}
                <div
                  className="absolute -right-3 -top-3 flex items-center gap-1.5 rounded-full bg-[#43614a] px-4 py-2 shadow-lg"
                  style={{
                    opacity: Math.min(1, progress * 4),
                    transform: `scale(${0.5 + Math.min(1, progress * 3) * 0.5})`,
                  }}
                >
                  <Check className="h-4 w-4 text-white" strokeWidth={2.5} />
                  <span className="text-sm font-semibold text-white">Sent</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
