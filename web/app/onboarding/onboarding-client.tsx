'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { Loader2 } from 'lucide-react';
import { api, captureSessionFromURL, getSession } from '@/lib/api';
import { track, setGAUserId } from '@/lib/analytics';

import WelcomeStep from '@/components/onboarding/steps/WelcomeStep';
import AboutYouStep from '@/components/onboarding/steps/AboutYouStep';
import SchedulingContextStep, { type SchedulingContextData } from '@/components/onboarding/steps/SchedulingContextStep';
import PreferencesStep from '@/components/onboarding/steps/PreferencesStep';
import ModeChoiceStep from '@/components/onboarding/steps/ModeChoiceStep';
import GoogleConnectStep from '@/components/onboarding/steps/GoogleConnectStep';
import CalendarSelectStep from '@/components/onboarding/steps/CalendarSelectStep';
import ProcessingStep from '@/components/onboarding/steps/ProcessingStep';
import PaywallStep from '@/components/onboarding/steps/PaywallStep';

type Step = 'loading' | 'welcome' | 'about' | 'scheduling' | 'preferences' | 'mode' | 'paywall' | 'google' | 'calendars' | 'processing';

interface UserInfo {
  user_id: string;
  email: string;
  needs_reauth?: boolean;
}

type AgentStatus = Record<string, string>;

interface OnboardingClientProps {
  needsGoogle: boolean;
  checkoutStatus: string | null;
  modeParam: string | null;
}

const EMPTY_SCHEDULING_CONTEXT: SchedulingContextData = {
  calendarGoal: '',
  schedulingWith: '',
  pastTools: [],
  pastToolsOther: '',
};

export default function OnboardingClient({ needsGoogle, checkoutStatus, modeParam }: OnboardingClientProps) {
  const router = useRouter();
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<Step>('loading');
  const [failed, setFailed] = useState(false);
  const [failedError, setFailedError] = useState<string | null>(null);
  const [agents, setAgents] = useState<AgentStatus | null>(null);

  // Profile data collected during onboarding
  const [jobTitle, setJobTitle] = useState('');
  const [schedulingContext, setSchedulingContext] = useState<SchedulingContextData>(EMPTY_SCHEDULING_CONTEXT);
  const [preferences, setPreferences] = useState<string[]>([]);
  const [mode, setMode] = useState<'bot' | 'draft'>(
    modeParam === 'bot' || modeParam === 'draft' ? modeParam : 'bot'
  );

  // Initial auth check
  useEffect(() => {
    captureSessionFromURL();
    api<UserInfo>('/auth/me')
      .then((data) => {
        if (data.needs_reauth) {
          const connectUrl = `${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/google/connect?token=${getSession()}`;
          window.location.href = `/permissions-required?retry_url=${encodeURIComponent(connectUrl)}`;
          return;
        }
        setUser(data);
        setGAUserId(data.user_id);
        track('page_view', { page: 'onboarding' });
        setLoading(false);
      })
      .catch(() => {
        setError('not_authenticated');
        setLoading(false);
      });
  }, []);

  // Determine initial step based on state
  useEffect(() => {
    if (!user) return;

    // Returning from Stripe checkout — go straight to Google connect
    if (checkoutStatus === 'success') {
      api<{ connected: boolean }>('/web/api/v1/onboarding/status')
        .then((status) => {
          setStep(status.connected ? 'calendars' : 'google');
        })
        .catch(() => setStep('google'));
      return;
    }

    if (needsGoogle) {
      // Fresh from Auth0 — check if they already have a subscription (returning user who paid but didn't connect Google)
      api<{ subscription_status: string }>('/web/api/v1/billing/status')
        .then((billing) => {
          const hasSubscription = billing.subscription_status === 'trialing' || billing.subscription_status === 'active';
          if (hasSubscription) {
            // Already paid — skip straight to Google connect
            setStep('google');
          } else {
            setStep('welcome');
          }
        })
        .catch(() => setStep('welcome'));
    } else {
      Promise.all([
        api<{ ready: boolean; connected: boolean }>('/web/api/v1/onboarding/status'),
        api<{ subscription_status: string }>('/web/api/v1/billing/status'),
      ])
        .then(([status, billing]) => {
          const hasSubscription = billing.subscription_status === 'trialing' || billing.subscription_status === 'active';
          if (status.ready && hasSubscription) {
            router.push('/settings');
          } else if (status.ready && !hasSubscription) {
            setStep('paywall');
          } else if (status.connected) {
            setStep('calendars');
          } else if (hasSubscription) {
            // Has subscription but no Google — go to Google connect
            setStep('google');
          } else {
            setStep('welcome');
          }
        })
        .catch(() => setStep('processing'));
    }
  }, [user, needsGoogle, checkoutStatus]);

  // Poll onboarding status when on the processing step
  const checkStatus = useCallback(async () => {
    try {
      const status = await api<{
        ready: boolean;
        failed?: boolean;
        error?: string;
        agents?: AgentStatus;
      }>('/web/api/v1/onboarding/status');
      if (status.agents) setAgents(status.agents);
      if (status.ready) {
        track('onboarding_completed');
        router.push('/settings');
      } else if (status.failed) {
        track('onboarding_failed', { error: status.error });
        setFailed(true);
        setFailedError(status.error || null);
      }
    } catch {
      // ignore — will retry on next poll
    }
  }, []);

  useEffect(() => {
    if (step !== 'processing' || !user || failed) return;
    checkStatus();
    const interval = setInterval(checkStatus, 3_000);
    return () => clearInterval(interval);
  }, [step, user, failed, checkStatus]);

  const handleRetry = useCallback(async () => {
    setFailed(false);
    setFailedError(null);
    try {
      await api('/api/v1/onboarding/run', { method: 'POST' });
    } catch {
      // will pick up failure on next poll
    }
  }, []);

  // Submit profile to backend
  const submitProfile = useCallback(async (selectedMode: 'bot' | 'draft') => {
    const tools = schedulingContext.pastTools
      .map(t => t === '__other__' ? schedulingContext.pastToolsOther || 'Other' : t)
      .filter(Boolean);

    const contextParts = [
      schedulingContext.calendarGoal && `Calendar goal: ${schedulingContext.calendarGoal}`,
      schedulingContext.schedulingWith && `Scheduling with: ${schedulingContext.schedulingWith}`,
      tools.length > 0 && `Past tools: ${tools.join(', ')}`,
      preferences.length > 0 && `Preferences: ${preferences.join(', ')}`,
    ].filter(Boolean);

    try {
      await api('/web/api/v1/onboarding/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_title: jobTitle || null,
          scheduling_context: contextParts.join('\n') || null,
          scheduling_mode: selectedMode,
        }),
      });
    } catch {
      // non-critical — proceed anyway
    }
  }, [jobTitle, schedulingContext, preferences]);

  if (loading || step === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white">
        <div className="text-center">
          <h1 className="font-[family-name:var(--font-space-grotesk)] text-2xl font-bold text-gray-900">
            Sign in required
          </h1>
          <p className="mt-2 text-gray-500">
            Please sign up to get started.
          </p>
          <a
            href={`${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/login`}
            className="mt-6 inline-flex items-center rounded-xl bg-[#43614a] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#527559]"
          >
            Sign Up with Google
          </a>
        </div>
      </div>
    );
  }

  // Step progress indicator
  const stepOrder: Step[] = ['welcome', 'about', 'scheduling', 'preferences', 'mode', 'paywall', 'google', 'calendars', 'processing'];
  const currentIndex = stepOrder.indexOf(step);

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#FAFAFA]">
      <div className="mx-auto max-w-lg px-4 py-8">
        <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm sm:p-10">
          {/* Header */}
          <div className="mb-6 flex items-center gap-3">
            <Image
              src="/scheduled_icon.svg"
              alt="Scheduled Logo"
              width={40}
              height={40}
              className="h-10 w-10"
            />
            <span className="font-[family-name:var(--font-space-grotesk)] text-2xl font-bold text-gray-900">
              Scheduled
            </span>
          </div>

          {/* Progress dots */}
          {step !== 'paywall' && step !== 'processing' && (
            <div className="mb-8 flex items-center gap-1.5">
              {stepOrder.slice(0, -1).map((s, i) => (
                <div
                  key={s}
                  className={`h-1 flex-1 rounded-full transition-colors ${
                    i <= currentIndex ? 'bg-[#43614a]' : 'bg-gray-200'
                  }`}
                />
              ))}
            </div>
          )}

          {/* Steps */}
          {step === 'welcome' && (
            <WelcomeStep onContinue={() => setStep('about')} />
          )}

          {step === 'about' && (
            <AboutYouStep
              initialValue={jobTitle}
              onContinue={(value) => {
                setJobTitle(value);
                setStep('scheduling');
              }}
              onBack={() => setStep('welcome')}
            />
          )}

          {step === 'scheduling' && (
            <SchedulingContextStep
              initialValue={schedulingContext}
              onContinue={(data) => {
                setSchedulingContext(data);
                setStep('preferences');
              }}
              onBack={() => setStep('about')}
            />
          )}

          {step === 'preferences' && (
            <PreferencesStep
              initialValue={preferences}
              onContinue={(selected) => {
                setPreferences(selected);
                setStep('mode');
              }}
              onBack={() => setStep('scheduling')}
            />
          )}

          {step === 'mode' && (
            <ModeChoiceStep
              initialMode={mode}
              onContinue={async (selectedMode) => {
                setMode(selectedMode);
                await submitProfile(selectedMode);
                setStep('paywall');
              }}
              onBack={() => setStep('preferences')}
            />
          )}

          {step === 'paywall' && user && (
            <PaywallStep email={user.email} />
          )}

          {step === 'google' && user && (
            <GoogleConnectStep email={user.email} mode={mode} />
          )}

          {step === 'calendars' && (
            <CalendarSelectStep onContinue={() => setStep('processing')} />
          )}

          {step === 'processing' && user && (
            <ProcessingStep
              agents={agents}
              failed={failed}
              failedError={failedError}
              onRetry={handleRetry}
              email={user.email}
              mode={mode}
            />
          )}
        </div>
      </div>
    </div>
  );
}
