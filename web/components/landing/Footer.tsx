'use client';

import Image from 'next/image';

export default function Footer() {
  return (
    <footer
      className="relative border-t border-gray-200 bg-[#FAFAFA]"
      style={{ zIndex: 10 }}
    >
      <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-10 md:grid-cols-2 lg:grid-cols-4">
          {/* Company Info */}
          <div className="col-span-1">
            <div className="mb-4 flex items-center gap-2">
              <Image
                src="/logo.png"
                alt="Stash Logo"
                width={32}
                height={32}
                className="h-8 w-8"
              />
              <span className="font-[family-name:var(--font-space-grotesk)] text-xl font-bold text-gray-900">
                Stash
              </span>
            </div>
            <p className="text-sm text-gray-500">
              AI-powered scheduling agent that handles your email scheduling automatically.
            </p>
            <p className="mt-4 text-xs text-gray-400">
              &copy; 2026 Fergana Labs. All rights reserved.
            </p>
          </div>

          {/* Product */}
          <div>
            <h3 className="mb-4 text-sm font-semibold tracking-wide text-gray-900 uppercase">
              Product
            </h3>
            <div className="flex flex-col gap-3 text-sm text-gray-500">
              <a
                href="#how-it-works"
                className="transition-colors hover:text-gray-900"
              >
                How It Works
              </a>
              <a
                href="#features"
                className="transition-colors hover:text-gray-900"
              >
                Features
              </a>
              <a
                href="#faq"
                className="transition-colors hover:text-gray-900"
              >
                FAQ
              </a>
            </div>
          </div>

          {/* Company */}
          <div>
            <h3 className="mb-4 text-sm font-semibold tracking-wide text-gray-900 uppercase">
              Company
            </h3>
            <div className="flex flex-col gap-3 text-sm text-gray-500">
              <a
                href="https://ferganalabs.com"
                target="_blank"
                rel="noopener noreferrer"
                className="transition-colors hover:text-gray-900"
              >
                Fergana Labs
              </a>
              <a
                href="mailto:hi@ferganalabs.com"
                className="transition-colors hover:text-gray-900"
              >
                Contact
              </a>
              <a
                href="/blog"
                className="transition-colors hover:text-gray-900"
              >
                Blog
              </a>
            </div>
          </div>

          {/* Legal */}
          <div>
            <h3 className="mb-4 text-sm font-semibold tracking-wide text-gray-900 uppercase">
              Legal
            </h3>
            <div className="flex flex-col gap-3 text-sm text-gray-500">
              <a
                href="/privacy"
                className="transition-colors hover:text-gray-900"
              >
                Privacy Policy
              </a>
              <a
                href="/terms"
                className="transition-colors hover:text-gray-900"
              >
                Terms of Service
              </a>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
