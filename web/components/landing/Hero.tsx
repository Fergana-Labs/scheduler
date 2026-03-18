'use client';

import { ArrowRight } from 'lucide-react';

const incomingText =
  "Hey are you free this week? I'd love to grab coffee and catch up, maybe Thursday or Friday works? Let me know what times are good for you, I'm pretty flexible...   ";

const draftText =
  "Hey! Thursday works great — how about 2pm at Blue Bottle on Market St? I'm also free Friday morning if that's easier. Looking forward to it!   ";

function MarqueeText({
  pathId,
  text,
  fill,
  fontSize,
  fontWeight,
  dur,
  startFrom,
  startTo,
}: {
  pathId: string;
  text: string;
  fill: string;
  fontSize: number;
  fontWeight?: number;
  dur: string;
  startFrom: string;
  startTo: string;
}) {
  // Repeat text to fill the gap
  const repeated = `${text}${text}${text}`;
  return (
    <text
      fill={fill}
      fontSize={fontSize}
      fontWeight={fontWeight}
      fontFamily="var(--font-geist-sans), system-ui, sans-serif"
    >
      <textPath href={`#${pathId}`} startOffset={startFrom}>
        <animate
          attributeName="startOffset"
          from={startFrom}
          to={startTo}
          dur={dur}
          repeatCount="indefinite"
        />
        {repeated}
      </textPath>
    </text>
  );
}

export default function Hero() {
  return (
    <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6">
      {/* Flowing text ribbon - behind content */}
      <div className="pointer-events-none absolute inset-0">
        <svg
          className="absolute inset-0 h-full w-full"
          viewBox="0 0 1400 900"
          preserveAspectRatio="xMidYMid slice"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <path
              id="curve-upper"
              d="M -400,190 C 0,40 300,280 700,130 C 1100,-20 1300,250 1800,110"
              fill="none"
            />
            <path
              id="curve-lower"
              d="M -400,780 C 50,640 300,830 700,730 C 1100,630 1250,810 1800,710"
              fill="none"
            />
          </defs>

          {/* Incoming email - upper curve, flowing right to left */}
          <MarqueeText
            pathId="curve-upper"
            text={incomingText}
            fill="#00000012"
            fontSize={21}
            dur="45s"
            startFrom="100%"
            startTo="-100%"
          />

          {/* Draft reply - lower curve, flowing left to right */}
          <MarqueeText
            pathId="curve-lower"
            text={draftText}
            fill="#00000010"
            fontSize={23}
            fontWeight={600}
            dur="40s"
            startFrom="-100%"
            startTo="100%"
          />
        </svg>
      </div>

      {/* Main content */}
      <div className="relative z-10 mx-auto max-w-4xl text-center">
        <h1 className="font-[family-name:var(--font-playfair)] text-5xl font-normal italic leading-[1.1] tracking-tight text-gray-900 sm:text-7xl lg:text-8xl">
          Just hit
          <br />
          send
        </h1>

        <p className="mx-auto mt-8 max-w-lg text-lg leading-relaxed text-gray-500 sm:text-xl">
          An AI that reads your calendar and suggests times
          that work — so you never have to check yourself.
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
