'use client';

import Header from './Header';
import Footer from './Footer';
import Hero from './Hero';
import OpenSource from './OpenSource';

export default function LandingPage() {
  return (
    <div className="relative min-h-screen bg-[#F5F0E8]">
      <Header />
      <Hero />
      <OpenSource />
      <Footer />
    </div>
  );
}
