import OnboardingClient from './onboarding-client';

interface OnboardingPageProps {
  searchParams?: {
    needs_google?: string | string[];
  };
}

export default function OnboardingPage({ searchParams }: OnboardingPageProps) {
  const rawNeedsGoogle = searchParams?.needs_google;
  const needsGoogle = Array.isArray(rawNeedsGoogle)
    ? rawNeedsGoogle.includes('1')
    : rawNeedsGoogle === '1';

  return <OnboardingClient needsGoogle={needsGoogle} />;
}
