'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { Loader2 } from 'lucide-react';
import { api, captureSessionFromURL, clearSession } from '@/lib/api';
import ReadyState from '@/components/onboarding/ReadyState';
import DisconnectedState from '@/components/onboarding/DisconnectedState';

interface UserInfo {
  user_id: string;
  email: string;
}

interface Settings {
  system_enabled: boolean;
  autopilot_enabled: boolean;
  process_sales_emails: boolean;
  stash_branding_enabled: boolean;
  stash_calendar_id: string | null;
  guides: { name: string; content: string; updated_at: string }[];
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
      } catch {
        // No valid session — clear stale token and redirect to sign-in
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

  const readySettings = settings;

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

          <p className="mb-6 text-sm text-gray-500">
            Signed in as{' '}
            <span className="font-medium text-gray-700">{user.email}</span>
          </p>

          {disconnected ? (
            <>
              <h1 className="mb-6 text-xl font-semibold text-gray-900">
                Account disconnected
              </h1>
              <DisconnectedState />
            </>
          ) : readySettings ? (
            <ReadyState
              systemEnabled={readySettings.system_enabled}
              autopilotEnabled={readySettings.autopilot_enabled}
              processSalesEmails={readySettings.process_sales_emails}
              brandingEnabled={readySettings.stash_branding_enabled}
              calendarId={readySettings.stash_calendar_id}
              guides={readySettings.guides}
              onDisconnected={handleDisconnected}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
