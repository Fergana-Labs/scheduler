'use client';

export default function Footer() {
  return (
    <footer className="border-t border-gray-200/50">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6 sm:px-8">
        <div className="flex items-center gap-2.5">
          <img
            src="/scheduled_logo.svg"
            alt="Scheduled"
            className="h-3"
          />
          <span className="text-sm text-gray-400">
            &copy; 2026 Fergana Labs
          </span>
        </div>

        <div className="flex items-center gap-6 text-sm text-gray-400">
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
