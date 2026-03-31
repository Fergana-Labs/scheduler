'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Header from './Header';
import Footer from './Footer';
import Hero from './Hero';
import OpenSource from './OpenSource';
import { trackPageEvent } from '@/lib/analytics';

const ERROR_MESSAGES: Record<string, string> = {
  missing_permissions:
    "Your Google account is missing required permissions. If you're using a work account, your IT admin may need to allow Calendar and Gmail access for this app.",
};

const DEFAULT_ERROR_MESSAGE =
  'Something went wrong connecting your Google account. Please try again.';

export default function LandingPage() {
  const searchParams = useSearchParams();
  const errorParam = searchParams.get('error');
  const errorMessage = errorParam ? ERROR_MESSAGES[errorParam] || DEFAULT_ERROR_MESSAGE : null;
  const [showBanner, setShowBanner] = useState(!!errorMessage);

  useEffect(() => {
    trackPageEvent('landing_page_view');
  }, []);

  return (
    <div className="relative min-h-screen bg-[#F5F0E8]">
      {showBanner && errorMessage && (
        <div className="flex items-center justify-between gap-3 bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-800">
          <p>{errorMessage}</p>
          <button
            onClick={() => setShowBanner(false)}
            className="shrink-0 text-red-600 hover:text-red-800"
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      )}
      <Header />
      <Hero />
      <OpenSource />
      <Footer />
    </div>
  );
}
