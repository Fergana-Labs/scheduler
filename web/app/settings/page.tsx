'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { AlertTriangle, Loader2, LogOut } from 'lucide-react';
import { api, captureSessionFromURL, clearSession, getSession } from '@/lib/api';
import { track, setGAUserId } from '@/lib/analytics';
import ReadyState from '@/components/onboarding/ReadyState';
import DisconnectedState from '@/components/onboarding/DisconnectedState';

interface UserInfo {
  user_id: string;
  email: string;
  google_email?: string | null;
  needs_reauth?: boolean;
}

interface Settings {
  system_enabled: boolean;
  autopilot_enabled: boolean;
  process_sales_emails: boolean;
  scheduled_branding_enabled: boolean;
  reasoning_emails_enabled: boolean;
  draft_auto_delete_enabled: boolean;
  scheduled_calendar_id: string | null;
  guides: { name: string; content: string; updated_at: string }[];
  scheduling_mode: string;
}

export default function SettingsPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserInfo | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [disconnected, setDisconnected] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    captureSessionFromURL();
    async function init() {
      try {
        const userInfo = await api<UserInfo>('/auth/me');
        setUser(userInfo);
        setGAUserId(userInfo.user_id);
        track('page_view', { page: 'settings' });

        if (userInfo.needs_reauth) {
          const connectUrl = `${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/google/connect?token=${getSession()}`;
          router.replace(`/permissions-required?retry_url=${encodeURIComponent(connectUrl)}`);
          return;
        }

        const status = await api<{ ready: boolean; connected: boolean }>('/web/api/v1/onboarding/status');
        if (!status.connected) {
          setDisconnected(true);
          setSettings(null);
          return;
        }

        if (!status.ready) {
          router.replace('/onboarding');
          return;
        }

        const s = await api<Settings>('/web/api/v1/settings');
        setSettings(s);
      } catch (err) {
        if (err instanceof Error && err.message === 'subscription_required') {
          // Subscription lapsed — show paywall (session is still valid in localStorage)
          router.replace('/onboarding');
          return;
        }
        // Auth failed — only clear session if /auth/me itself failed (not a downstream call)
        clearSession();
        window.location.href = `${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/login`;
        return;
      } finally {
        setLoading(false);
      }
    }
    init();
  }, [router]);

  function handleDisconnected() {
    setDisconnected(true);
    setSettings(null);
  }

  if (loading || !user || (!disconnected && !settings)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
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

          <div className="mb-6 flex items-center justify-between">
            <p className="text-sm text-gray-500">
              Signed in as{' '}
              <span className="font-medium text-gray-700">{user.email}</span>
            </p>
            <button
              onClick={() => {
                clearSession();
                window.location.href = `${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/logout`;
              }}
              className="flex cursor-pointer items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
            >
              <LogOut className="h-3.5 w-3.5" />
              Sign out
            </button>
          </div>

          {user.google_email && user.google_email !== user.email && (
            <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4">
              <div className="flex items-start gap-3">
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-amber-100">
                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    Scheduled will monitor {user.google_email} for incoming emails.
                  </p>
                  <p className="mt-0.5 text-xs text-gray-500">
                    This differs from your sign-in email ({user.email}).
                  </p>
                </div>
              </div>
            </div>
          )}

          {disconnected ? (
            <>
              <h1 className="mb-6 text-xl font-semibold text-gray-900">
                Account disconnected
              </h1>
              <DisconnectedState />
            </>
          ) : settings ? (
            <ReadyState
              systemEnabled={settings.system_enabled}
              autopilotEnabled={settings.autopilot_enabled}
              processSalesEmails={settings.process_sales_emails}
              brandingEnabled={settings.scheduled_branding_enabled}
              reasoningEmailsEnabled={settings.reasoning_emails_enabled}
              draftAutoDeleteEnabled={settings.draft_auto_delete_enabled}
              calendarId={settings.scheduled_calendar_id}
              guides={settings.guides}
              schedulingMode={settings.scheduling_mode}
              onDisconnected={handleDisconnected}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
