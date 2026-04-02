import OnboardingClient from './onboarding-client';

interface OnboardingPageProps {
  searchParams?: {
    needs_google?: string | string[];
    checkout?: string | string[];
    mode?: string | string[];
  };
}

export default function OnboardingPage({ searchParams }: OnboardingPageProps) {
  const rawNeedsGoogle = searchParams?.needs_google;
  const needsGoogle = Array.isArray(rawNeedsGoogle)
    ? rawNeedsGoogle.includes('1')
    : rawNeedsGoogle === '1';

  const rawCheckout = searchParams?.checkout;
  const checkoutStatus = Array.isArray(rawCheckout)
    ? rawCheckout[0] || null
    : rawCheckout || null;

  const rawMode = searchParams?.mode;
  const modeParam = Array.isArray(rawMode) ? rawMode[0] || null : rawMode || null;

  return (
    <OnboardingClient
      needsGoogle={needsGoogle}
      checkoutStatus={checkoutStatus}
      modeParam={modeParam}
    />
  );
}
