'use client';

export default function Footer() {
  return (
    <footer className="border-t border-gray-200/50">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-4 text-sm text-gray-400 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div className="flex items-center justify-center gap-2.5 sm:justify-start">
          <img
            src="/scheduled_logo.svg"
            alt="Scheduled"
            className="h-3"
          />
          <span className="text-xs text-gray-400 sm:text-sm">
            &copy; 2026{' '}
            <a
              href="https://ferganalabs.com"
              target="_blank"
              rel="noopener noreferrer"
              className="transition-colors hover:text-gray-600"
            >
              Fergana Labs
            </a>
          </span>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-3 text-gray-400 sm:gap-6 sm:text-sm">
          <a href="/privacy" className="transition-colors hover:text-gray-600">
            Privacy
          </a>
          <a href="/terms" className="transition-colors hover:text-gray-600">
            Terms
          </a>
          <a
            href="mailto:hi@ferganalabs.com"
            className="transition-colors hover:text-gray-600"
          >
            Contact
          </a>
        </div>
      </div>
    </footer>
  );
}
