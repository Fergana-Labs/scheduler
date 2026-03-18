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
          href="mailto:henry@ferganalabs.com"
          className="text-sm text-gray-500 transition-colors hover:text-gray-900"
        >
          Contact
        </a>
      </nav>
    </header>
  );
}
