'use client';

export default function OpenSource() {
  return (
    <section className="relative px-4 py-20 sm:px-6 sm:py-28 lg:py-32">
      <div className="mx-auto max-w-3xl text-center">
        <p className="text-sm font-medium uppercase tracking-widest text-[#43614a]">
          Open Source
        </p>
        <h2 className="font-[family-name:var(--font-playfair)] mt-4 text-3xl font-normal italic tracking-tight text-gray-900 sm:text-4xl lg:text-5xl">
          Built in the open
        </h2>
        <p className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-gray-500 sm:text-lg">
          Scheduled is fully open source. Read the code, run it yourself,
          or contribute — your calendar data is yours.
        </p>

        <div className="mt-10 flex items-center justify-center gap-5">
          <a
            href="https://github.com/Fergana-Labs/scheduler"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-[44px] w-full items-center justify-center gap-2.5 rounded-full border border-gray-900 px-7 py-3.5 text-base font-medium text-gray-900 transition-all hover:bg-gray-900 hover:text-white sm:w-auto"
          >
            <svg
              className="h-5 w-5"
              fill="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                clipRule="evenodd"
              />
            </svg>
            View on GitHub
          </a>
        </div>
      </div>
    </section>
  );
}
