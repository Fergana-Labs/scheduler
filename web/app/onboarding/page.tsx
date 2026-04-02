import OnboardingClient from './onboarding-client';

interface OnboardingPageProps {
  searchParams?: {
    needs_google?: string | string[];
    checkout?: string | string[];
    mode?: string | string[];
  };
}

function first(val: string | string[] | undefined): string | null {
  return Array.isArray(val) ? val[0] || null : val || null;
}

export default function OnboardingPage({ searchParams }: OnboardingPageProps) {
  const rawNeedsGoogle = searchParams?.needs_google;
  const needsGoogle = Array.isArray(rawNeedsGoogle)
    ? rawNeedsGoogle.includes('1')
    : rawNeedsGoogle === '1';

  const checkoutStatus = first(searchParams?.checkout);
  const modeParam = first(searchParams?.mode);

  return (
    <OnboardingClient
      needsGoogle={needsGoogle}
      checkoutStatus={checkoutStatus}
      modeParam={modeParam}
    />
  );
}
