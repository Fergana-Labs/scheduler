import type { Metadata } from 'next';
import { GoogleAnalytics } from '@next/third-parties/google';
import { Geist, Geist_Mono, Space_Grotesk, Playfair_Display } from 'next/font/google';
import './globals.css';

const gaId = process.env.NEXT_PUBLIC_GA_ID;

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

const spaceGrotesk = Space_Grotesk({
  variable: '--font-space-grotesk',
  subsets: ['latin'],
});

const playfairDisplay = Playfair_Display({
  variable: '--font-playfair',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: 'Scheduled - AI Email Scheduling Agent',
  description:
    'AI-powered scheduling agent that reads your emails, checks your calendar, and drafts perfect replies. Stop the back-and-forth — let AI handle your scheduling.',
  keywords: [
    'AI scheduling assistant',
    'email scheduling automation',
    'AI calendar management',
    'automatic meeting scheduler',
    'AI email responder',
    'smart scheduling',
    'calendar AI agent',
    'meeting scheduling automation',
    'AI scheduling agent',
    'email scheduling bot',
    'automated meeting booking',
  ],
  authors: [{ name: 'Fergana Labs' }],
  creator: 'Fergana Labs',
  publisher: 'Fergana Labs',
  metadataBase: new URL('https://scheduler.ferganalabs.com'),
  alternates: {
    canonical: '/',
  },
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: 'https://scheduler.ferganalabs.com',
    title: 'Scheduled - AI Email Scheduling Agent',
    description:
      'AI-powered scheduling agent that reads your emails, checks your calendar, and drafts perfect replies automatically.',
    siteName: 'Scheduled',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Scheduled - AI Email Scheduling Agent',
    description:
      'AI-powered scheduling agent that reads your emails, checks your calendar, and drafts perfect replies automatically.',
  },
  icons: {
    icon: '/scheduled_icon.svg',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} ${spaceGrotesk.variable} ${playfairDisplay.variable} antialiased`}
        suppressHydrationWarning
      >
        <main className="bg-white">
          {children}
        </main>
        {gaId && <GoogleAnalytics gaId={gaId} />}
      </body>
    </html>
  );
}
