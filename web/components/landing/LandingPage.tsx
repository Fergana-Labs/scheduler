'use client';

import { useEffect } from 'react';
import Header from './Header';
import Footer from './Footer';
import Hero from './Hero';
import Features from './Features';
import Pricing from './Pricing';
import OpenSource from './OpenSource';
import { trackPageEvent } from '@/lib/analytics';

export default function LandingPage() {
  useEffect(() => {
    trackPageEvent('landing_page_view');
  }, []);

  return (
    <div className="relative min-h-screen bg-[#F5F0E8]">
      <Header />
      <Hero />
      <Features />
      <Pricing />
      <OpenSource />
      <Footer />
    </div>
  );
}
