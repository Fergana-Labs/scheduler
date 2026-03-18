import LandingPage from '@/components/landing/LandingPage';

export default function Home() {
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'Scheduled',
    applicationCategory: 'BusinessApplication',
    operatingSystem: 'Web',
    description:
      'AI-powered scheduling agent that monitors your Gmail, classifies scheduling requests, checks your calendar availability, and drafts personalized reply emails automatically.',
    offers: {
      '@type': 'Offer',
      price: '0',
      priceCurrency: 'USD',
    },
    featureList: [
      'Gmail Monitoring',
      'Intent Classification',
      'Calendar Availability Checking',
      'Automated Draft Composition',
      'Email Style Learning',
      'Scheduling Preference Learning',
      'Multi-Calendar Support',
      'Real-Time Push Notifications',
    ],
    softwareVersion: '1.0.0',
    author: {
      '@type': 'Organization',
      name: 'Fergana Labs',
    },
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <LandingPage />
    </>
  );
}
