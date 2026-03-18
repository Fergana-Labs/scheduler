'use client';

import { useRef, useState, useEffect, useCallback } from 'react';
import { ArrowRight, Mail, MailOpen, Inbox, Send, Reply, Forward, Calendar, Clock, Bell, CalendarCheck, CalendarDays, Timer, Video, Users } from 'lucide-react';

const upperIcons = [Mail, MailOpen, Inbox, Send, Reply, Forward, Mail, Send, MailOpen, Inbox, Reply, Forward, Mail, MailOpen, Send, Reply, Forward, Inbox, Mail, Send];
const lowerIcons = [Calendar, Clock, Bell, CalendarCheck, CalendarDays, Timer, Video, Users, Calendar, Clock, Bell, CalendarCheck, CalendarDays, Timer, Video, Users, Calendar, Clock, Bell, CalendarCheck];

const UPPER_PATH = "path('M -200,100 C 50,20 180,200 420,60 C 580,-30 700,150 900,80 C 1080,20 1200,160 1400,70 C 1550,10 1650,130 1750,80')";
const LOWER_PATH = "path('M -200,760 C 80,710 200,800 380,770 C 560,740 650,830 820,790 C 1000,750 1100,820 1250,780 C 1400,740 1550,810 1750,760')";

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


// Pixel-art "SENT!" rendered as SVG blocks, matching the favicon style
function PixelSent() {
  const p = 4; // pixel size
  const g = 1; // gap between pixels within a letter
  const s = p + g; // stride
  const color = '#43614a';
  const letterSpacing = p * 1.5; // clear gap between letters

  // Each letter on a 5-col x 5-row grid for clarity
  const letters: { char: string; w: number; pixels: [number, number][] }[] = [
    { char: 'S', w: 4, pixels: [
      [1,0],[2,0],[3,0],
      [0,1],
      [0,2],[1,2],[2,2],[3,2],
                        [3,3],
      [0,4],[1,4],[2,4],
    ]},
    { char: 'E', w: 4, pixels: [
      [0,0],[1,0],[2,0],[3,0],
      [0,1],
      [0,2],[1,2],[2,2],
      [0,3],
      [0,4],[1,4],[2,4],[3,4],
    ]},
    { char: 'N', w: 4, pixels: [
      [0,0],            [3,0],
      [0,1],[1,1],      [3,1],
      [0,2],      [2,2],[3,2],
      [0,3],            [3,3],
      [0,4],            [3,4],
    ]},
    { char: 'T', w: 5, pixels: [
      [0,0],[1,0],[2,0],[3,0],[4,0],
                  [2,1],
                  [2,2],
                  [2,3],
                  [2,4],
    ]},
    { char: '!', w: 1, pixels: [
      [0,0],
      [0,1],
      [0,2],
      [0,4],
    ]},
  ];

  // Calculate total width
  let totalW = 0;
  const offsets: number[] = [];
  letters.forEach((l, i) => {
    offsets.push(totalW);
    totalW += l.w * s;
    if (i < letters.length - 1) totalW += letterSpacing;
  });
  const totalH = 5 * s;

  return (
    <svg width={totalW} height={totalH} viewBox={`0 0 ${totalW} ${totalH}`} className="drop-shadow-md">
      {letters.map((l, li) => (
        l.pixels.map(([cx, cy], pi) => (
          <rect
            key={`${li}-${pi}`}
            x={offsets[li] + cx * s}
            y={cy * s}
            width={p}
            height={p}
            rx={1}
            fill={color}
          />
        ))
      ))}
    </svg>
  );
}

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
  const cardContainerRef = useRef<HTMLDivElement>(null);
  const [cardStates, setCardStates] = useState<number[]>(EMAILS.map(() => 0));
  // Distance from section top to card container top — measured once
  const cardOffsetRef = useRef<number>(0);

  useEffect(() => {
    if (!sectionRef.current || !cardContainerRef.current) return;
    // Measure initial card position relative to section
    const sectionRect = sectionRef.current.getBoundingClientRect();
    const cardRect = cardContainerRef.current.getBoundingClientRect();
    cardOffsetRef.current = cardRect.top - sectionRect.top;
  }, []);

  const handleScroll = useCallback(() => {
    if (!sectionRef.current) return;

    const scrolled = Math.max(0, -sectionRef.current.getBoundingClientRect().top);

    // All cards must be fully dismissed by the time the card container's
    // top edge reaches the viewport top (i.e., starts going off-screen).
    const budget = Math.max(50, cardOffsetRef.current);
    const scrollPerCard = budget / EMAILS.length;

    const newStates = EMAILS.map((_, i) => {
      const cardStart = i * scrollPerCard;
      const cardEnd = cardStart + scrollPerCard;
      if (scrolled <= cardStart) return 0;
      if (scrolled >= cardEnd) return 1;
      return (scrolled - cardStart) / scrollPerCard;
    });

    setCardStates(newStates);
  }, []);

  useEffect(() => {
    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, [handleScroll]);

  return (
    <section
      ref={sectionRef}
      className="relative overflow-hidden px-4 pt-24 pb-14 sm:px-6 sm:pt-28"
    >
      {/* Flowing icon streams - behind everything */}
      <div className="pointer-events-none absolute inset-0">
        <div className="relative h-full w-full" style={{ transform: 'scale(1)', transformOrigin: 'top left' }}>
          <IconStream icons={upperIcons} offsetPath={UPPER_PATH} duration={40} opacity={0.14} />
          <IconStream icons={lowerIcons} offsetPath={LOWER_PATH} duration={45} opacity={0.12} reverse />
        </div>
      </div>

      {/* Two-column hero — scrolls naturally with the page */}
      <div className="relative z-10 mx-auto flex min-h-[calc(100svh-6rem)] w-full max-w-6xl flex-col gap-10 sm:gap-11 lg:min-h-screen lg:flex-row lg:items-center lg:gap-20">
        {/* Left: headline + CTA */}
        <div className="flex-1">
          <h1 className="font-[family-name:var(--font-playfair)] text-[clamp(2.5rem,10vw,4.5rem)] font-normal italic leading-[1.05] tracking-tight text-gray-900 sm:text-5xl lg:text-7xl xl:text-8xl">
            Just hit
            <br />
            send
          </h1>

          <p className="mt-8 max-w-sm text-base leading-relaxed text-gray-500 sm:max-w-md sm:text-lg">
            Scheduled is an open-source agent that lives in your email and automatically drafts responses.
          </p>

          <div className="mt-10">
            <a
              href={`${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/login?signup=1`}
              className="inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-full bg-[#43614a] px-7 py-3.5 text-base font-medium text-white transition-all hover:bg-[#527559] sm:w-auto"
            >
              Get Started
              <ArrowRight className="h-4 w-4" />
            </a>
          </div>
        </div>

        {/* Right: email card stack */}
        <div ref={cardContainerRef} className="relative hidden h-[420px] w-[440px] flex-shrink-0 lg:block">
          {EMAILS.map((email, i) => {
            const progress = cardStates[i] ?? 0;
            const isGone = progress >= 1;
            const stackIndex = EMAILS.length - 1 - i;
            const stackOffsetY = stackIndex * 4;
            const stackOffsetX = stackIndex * -3;

            const ease = progress * progress * (3 - 2 * progress);

            const translateX = ease * 900;
            const translateY = ease * -150;
            const rotate = ease * 28;
            const opacity = 1 - ease * 0.5;

            const transform = progress > 0
              ? `translate(${translateX}px, ${translateY}px) rotate(${rotate}deg)`
              : `translate(${stackOffsetX}px, ${stackOffsetY}px)`;

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
              </div>
            );
          })}

          {/* "SENT" pixel-art floaters — rises from top of stack like +10xp */}
          {EMAILS.map((_, i) => {
            const progress = cardStates[i] ?? 0;
            if (progress < 0.1) return null;

            const t = Math.min(1, (progress - 0.1) / 0.9);
            const fadeIn = Math.min(1, t * 6);
            const fadeOut = t > 0.4 ? Math.max(0, 1 - (t - 0.4) / 0.6) : 1;
            const rise = t * 120;
            const popScale = t < 0.2 ? 0.5 + t * 4 : (t < 0.35 ? 1.3 - (t - 0.2) * 2 : 1);

            return (
              <div
                key={`sent-${i}`}
                className="pointer-events-none absolute left-1/2 top-0"
                style={{
                  opacity: fadeIn * fadeOut,
                  transform: `translate(-50%, ${-20 - rise}px) scale(${popScale})`,
                  zIndex: 50 + i,
                }}
              >
                <PixelSent />
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
