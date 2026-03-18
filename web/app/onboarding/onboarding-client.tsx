'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { CheckCircle, Loader2 } from 'lucide-react';
import { api, captureSessionFromURL, getSession } from '@/lib/api';
import PendingState from '@/components/onboarding/PendingState';

interface UserInfo {
  user_id: string;
  email: string;
}

interface OnboardingClientProps {
  needsGoogle: boolean;
}

export default function OnboardingClient({ needsGoogle }: OnboardingClientProps) {
  const router = useRouter();
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    captureSessionFromURL();
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
        router.push('/settings');
      }
    } catch {
      // ignore — will retry on next poll
    }
  }, [router]);

  useEffect(() => {
    if (!user || needsGoogle) return;

    // Check immediately
    checkStatus();

    const interval = setInterval(checkStatus, 10_000);
    return () => clearInterval(interval);
  }, [user, needsGoogle, checkStatus]);

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
            href={`${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/login`}
            className="mt-6 inline-flex items-center rounded-xl bg-[#43614a] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#527559]"
          >
            Sign Up with Google
          </a>
        </div>
      </div>
    );
  }

  if (needsGoogle) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#FAFAFA]">
        <div className="mx-auto max-w-lg px-4">
          <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm sm:p-10">
            <div className="mb-8 flex items-center gap-3">
              <Image
                src="/logo.png"
                alt="Scheduled Logo"
                width={40}
                height={40}
                className="h-10 w-10"
              />
              <span className="font-[family-name:var(--font-space-grotesk)] text-2xl font-bold text-gray-900">
                Scheduled
              </span>
            </div>

            <div className="mb-8">
              <h1 className="text-xl font-semibold text-gray-900">
                Connect your Google account
              </h1>
              <p className="mt-2 text-sm text-gray-500">
                Signed in as{' '}
                <span className="font-medium text-gray-700">
                  {user?.email}
                </span>
              </p>
              <p className="mt-4 text-sm text-gray-500">
                Scheduled needs access to your Gmail and Calendar to draft scheduling replies.
              </p>
            </div>

            <a
              href={`${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/google/connect?token=${getSession() || ''}`}
              className="inline-flex w-full items-center justify-center rounded-xl bg-[#43614a] px-6 py-4 text-base font-semibold text-white transition-colors hover:bg-[#527559]"
            >
              Connect Google Account
            </a>
          </div>
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
              alt="Scheduled Logo"
              width={40}
              height={40}
              className="h-10 w-10"
            />
            <span className="font-[family-name:var(--font-space-grotesk)] text-2xl font-bold text-gray-900">
              Scheduled
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

          <PendingState />
        </div>
      </div>
    </div>
  );
}

