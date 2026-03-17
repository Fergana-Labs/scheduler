'use client';

import { useEffect, useState, useCallback } from 'react';
import Image from 'next/image';
import { CheckCircle, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import PendingState from '@/components/onboarding/PendingState';
import ReadyState from '@/components/onboarding/ReadyState';

interface UserInfo {
  user_id: string;
  email: string;
}

interface Settings {
  system_enabled: boolean;
  autopilot_enabled: boolean;
  stash_branding_enabled: boolean;
  stash_calendar_id: string | null;
  guides: { name: string; content: string; updated_at: string }[];
}

export default function OnboardingPage() {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [settings, setSettings] = useState<Settings | null>(null);

  useEffect(() => {
    api<UserInfo>('/auth/me')
      .then((data) => {
        setUser(data);
        setLoading(false);
      })
      .catch(() => {
        setError('not_authenticated');
        setLoading(false);
      });
  }, []);

  const checkStatus = useCallback(async () => {
    try {
      const status = await api<{ ready: boolean }>('/web/api/v1/onboarding/status');
      if (status.ready) {
        const s = await api<Settings>('/web/api/v1/settings');
        setSettings(s);
        setReady(true);
      }
    } catch {
      // ignore — will retry on next poll
    }
  }, []);

  useEffect(() => {
    if (!user || ready) return;

    // Check immediately
    checkStatus();

    const interval = setInterval(checkStatus, 10_000);
    return () => clearInterval(interval);
  }, [user, ready, checkStatus]);

  if (loading) {
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
            href={`${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/google`}
            className="mt-6 inline-flex items-center rounded-xl bg-[#43614a] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#527559]"
          >
            Sign Up with Google
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#FAFAFA]">
      <div className="mx-auto max-w-lg px-4">
        <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm sm:p-10">
          {/* Header */}
          <div className="mb-8 flex items-center gap-3">
            <Image
              src="/logo.png"
              alt="Stash Logo"
              width={40}
              height={40}
              className="h-10 w-10"
            />
            <span className="font-[family-name:var(--font-space-grotesk)] text-2xl font-bold text-gray-900">
              Stash
            </span>
          </div>

          {/* Success message */}
          <div className="mb-8 flex items-start gap-3">
            <CheckCircle className="mt-0.5 h-6 w-6 flex-shrink-0 text-[#43614a]" />
            <div>
              <h1 className="text-xl font-semibold text-gray-900">
                You&apos;re all set!
              </h1>
              <p className="mt-1 text-sm text-gray-500">
                Signed in as{' '}
                <span className="font-medium text-gray-700">
                  {user?.email}
                </span>
              </p>
            </div>
          </div>

          {/* Pending or Ready state */}
          {ready && settings ? (
            <ReadyState
              systemEnabled={settings.system_enabled}
              autopilotEnabled={settings.autopilot_enabled}
              brandingEnabled={settings.stash_branding_enabled}
              calendarId={settings.stash_calendar_id}
              guides={settings.guides}
            />
          ) : (
            <PendingState />
          )}
        </div>
      </div>
    </div>
  );
}
