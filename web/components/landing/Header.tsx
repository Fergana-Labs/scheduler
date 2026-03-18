'use client';

import { useRouter } from 'next/navigation';

export default function Header() {
  const router = useRouter();

  return (
    <header className="absolute top-0 left-0 right-0 z-10">
      <nav
        className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5 sm:px-8"
        aria-label="Global"
      >
        <button
          onClick={() => router.push('/')}
          className="flex cursor-pointer items-center gap-3 transition-opacity hover:opacity-70"
        >
          <span className="sr-only">Go to Scheduled homepage</span>
          <img
            src="/scheduled_logo.svg"
            alt="Scheduled"
            className="h-5"
          />
        </button>

        <a
          href={`${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/google`}
          className="rounded-full bg-gray-900 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-800"
        >
          Get Started
        </a>
      </nav>
    </header>
  );
}
