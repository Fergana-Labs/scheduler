'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import {
  Loader2,
  LogOut,
  ArrowLeft,
  Check,
  X,
  LinkIcon,
  Unlink,
  QrCode,
  Cookie,
} from 'lucide-react';
import { api, captureSessionFromURL, clearSession } from '@/lib/api';

interface UserInfo {
  user_id: string;
  email: string;
}

interface BotResponse {
  type: 'text' | 'image';
  body: string;
  url?: string;
  timestamp: number;
}

interface PlatformStatus {
  status: 'connected' | 'not_configured' | 'unknown' | 'pending';
  room_id?: string;
}

interface LoginSession {
  platform: string;
  status: 'initiating' | 'waiting_qr' | 'waiting_cookies' | 'polling' | 'connected' | 'error';
  botResponses: BotResponse[];
  error?: string;
}

const PLATFORMS = [
  {
    id: 'whatsapp',
    name: 'WhatsApp',
    loginType: 'qr' as const,
    color: 'bg-green-100 text-green-700 border-green-200',
    activeColor: 'bg-green-50 border-green-300',
    description: 'Scan a QR code with your phone to link WhatsApp.',
  },
  {
    id: 'instagram',
    name: 'Instagram',
    loginType: 'cookies' as const,
    color: 'bg-pink-100 text-pink-700 border-pink-200',
    activeColor: 'bg-pink-50 border-pink-300',
    description: 'Paste a cURL command from your browser to link Instagram.',
  },
  {
    id: 'linkedin',
    name: 'LinkedIn',
    loginType: 'cookies' as const,
    color: 'bg-blue-100 text-blue-700 border-blue-200',
    activeColor: 'bg-blue-50 border-blue-300',
    description: 'Paste a cURL command from your browser to link LinkedIn.',
  },
  {
    id: 'signal',
    name: 'Signal',
    loginType: 'qr' as const,
    color: 'bg-indigo-100 text-indigo-700 border-indigo-200',
    activeColor: 'bg-indigo-50 border-indigo-300',
    description: 'Scan a QR code with your phone to link Signal.',
  },
  {
    id: 'telegram',
    name: 'Telegram',
    loginType: 'qr' as const,
    color: 'bg-sky-100 text-sky-700 border-sky-200',
    activeColor: 'bg-sky-50 border-sky-300',
    description: 'Follow the bot instructions to link Telegram.',
  },
];

function CookieInstructions({ platform }: { platform: string }) {
  const platformName = platform === 'instagram' ? 'Instagram' : 'LinkedIn';
  const site = platform === 'instagram' ? 'instagram.com' : 'linkedin.com';

  return (
    <div className="rounded-lg bg-gray-50 p-4 text-sm text-gray-700">
      <p className="mb-2 font-medium">How to get your login cookies:</p>
      <ol className="list-inside list-decimal space-y-1.5 text-xs text-gray-600">
        <li>Open a <strong>private/incognito</strong> browser window</li>
        <li>Log in to <strong>{site}</strong></li>
        <li>Open DevTools (F12) → <strong>Network</strong> tab</li>
        <li>Filter for <strong>graphql</strong> requests</li>
        <li>Right-click any request → <strong>Copy → Copy as cURL</strong></li>
        <li>Paste the entire cURL command below</li>
      </ol>
    </div>
  );
}

function PlatformCard({
  platform,
  status,
  onConnect,
}: {
  platform: (typeof PLATFORMS)[number];
  status: PlatformStatus | undefined;
  onConnect: (platformId: string) => void;
}) {
  const isConnected = status?.status === 'connected';
  const isConfigured = status && status.status !== 'not_configured';

  return (
    <div
      className={`rounded-xl border bg-white p-5 shadow-sm transition-shadow hover:shadow-md ${
        isConnected ? platform.activeColor : 'border-gray-200'
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span
            className={`rounded-full px-3 py-1 text-sm font-medium ${platform.color}`}
          >
            {platform.name}
          </span>
          {isConnected && (
            <span className="flex items-center gap-1 text-xs text-green-600">
              <Check className="h-3 w-3" />
              Connected
            </span>
          )}
        </div>
        <button
          onClick={() => onConnect(platform.id)}
          className={`flex cursor-pointer items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
            isConnected
              ? 'border border-gray-300 text-gray-600 hover:bg-gray-50'
              : 'bg-gray-900 text-white hover:bg-gray-800'
          }`}
        >
          {isConnected ? (
            <>
              <Unlink className="h-3.5 w-3.5" />
              Reconnect
            </>
          ) : (
            <>
              <LinkIcon className="h-3.5 w-3.5" />
              Connect
            </>
          )}
        </button>
      </div>
    </div>
  );
}

function LoginModal({
  platform,
  session,
  onClose,
  onSendCookies,
}: {
  platform: (typeof PLATFORMS)[number];
  session: LoginSession;
  onClose: () => void;
  onSendCookies: (cookies: string) => void;
}) {
  const [cookieInput, setCookieInput] = useState('');

  const qrResponse = session.botResponses.find((r) => r.type === 'image');
  const textResponses = session.botResponses.filter((r) => r.type === 'text');
  const isConnected = session.status === 'connected';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-6 shadow-xl">
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-[family-name:var(--font-space-grotesk)] text-lg font-bold text-gray-900">
            Connect {platform.name}
          </h2>
          <button
            onClick={onClose}
            className="cursor-pointer rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Status indicator */}
        {session.status === 'initiating' && (
          <div className="mb-4 flex items-center gap-2 text-sm text-gray-500">
            <Loader2 className="h-4 w-4 animate-spin" />
            Connecting to {platform.name} bridge...
          </div>
        )}

        {isConnected && (
          <div className="mb-4 flex items-center gap-2 rounded-lg bg-green-50 p-3 text-sm text-green-700">
            <Check className="h-4 w-4" />
            Successfully connected to {platform.name}!
          </div>
        )}

        {session.error && (
          <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
            {session.error}
          </div>
        )}

        {/* QR Code (WhatsApp, Signal) */}
        {platform.loginType === 'qr' && (
          <div className="mb-4">
            {qrResponse?.url ? (
              <div className="flex flex-col items-center gap-3">
                <div className="rounded-lg border border-gray-200 bg-white p-4">
                  <img
                    src={qrResponse.url}
                    alt="QR Code"
                    className="h-64 w-64"
                  />
                </div>
                <p className="text-center text-sm text-gray-500">
                  Open {platform.name} on your phone → Settings → Linked
                  Devices → Scan this QR code
                </p>
              </div>
            ) : session.status !== 'initiating' && !isConnected ? (
              <div className="flex flex-col items-center gap-2 py-8">
                <QrCode className="h-12 w-12 text-gray-300" />
                <p className="text-sm text-gray-500">
                  Waiting for QR code from bridge...
                </p>
                <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
              </div>
            ) : null}
          </div>
        )}

        {/* Cookie input (Instagram, LinkedIn) */}
        {platform.loginType === 'cookies' && !isConnected && (
          <div className="mb-4">
            <CookieInstructions platform={platform.id} />
            <div className="mt-3">
              <textarea
                value={cookieInput}
                onChange={(e) => setCookieInput(e.target.value)}
                placeholder="Paste your cURL command here..."
                className="w-full rounded-lg border border-gray-300 p-3 text-xs font-mono text-gray-800 placeholder-gray-400 focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
                rows={6}
              />
              <button
                onClick={() => {
                  if (cookieInput.trim()) onSendCookies(cookieInput.trim());
                }}
                disabled={!cookieInput.trim() || session.status === 'polling'}
                className="mt-2 flex w-full cursor-pointer items-center justify-center gap-1.5 rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {session.status === 'polling' ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Cookie className="h-4 w-4" />
                )}
                Send Cookies
              </button>
            </div>
          </div>
        )}

        {/* Bot responses */}
        {textResponses.length > 0 && (
          <div className="mt-4 border-t border-gray-100 pt-4">
            <p className="mb-2 text-xs font-medium text-gray-400">
              Bridge bot messages
            </p>
            <div className="max-h-40 space-y-2 overflow-y-auto">
              {textResponses.map((r, i) => (
                <div
                  key={i}
                  className="rounded-md bg-gray-50 px-3 py-2 text-xs text-gray-700"
                >
                  {r.body}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Close button */}
        <div className="mt-6 flex justify-end">
          <button
            onClick={onClose}
            className="cursor-pointer rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50"
          >
            {isConnected ? 'Done' : 'Close'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ConnectionsPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [statuses, setStatuses] = useState<Record<string, PlatformStatus>>({});
  const [activeSession, setActiveSession] = useState<LoginSession | null>(null);
  const [activePlatform, setActivePlatform] = useState<string | null>(null);
  const [matrixConfigured, setMatrixConfigured] = useState(false);

  useEffect(() => {
    captureSessionFromURL();
    async function init() {
      try {
        const userInfo = await api<UserInfo>('/auth/me');
        setUser(userInfo);

        // Try to fetch bridge statuses
        try {
          const s = await api<Record<string, PlatformStatus>>(
            '/web/api/v1/bridges/status',
          );
          setStatuses(s);
          setMatrixConfigured(true);
        } catch {
          // Matrix not configured yet
          setMatrixConfigured(false);
        }
      } catch {
        clearSession();
        window.location.href = `${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/login`;
        return;
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  // Poll for status updates during active login
  useEffect(() => {
    if (!activeSession || !activePlatform) return;
    if (activeSession.status === 'connected' || activeSession.status === 'error') return;

    const interval = setInterval(async () => {
      try {
        const resp = await api<{
          status: string;
          bot_responses: BotResponse[];
        }>(`/web/api/v1/bridges/${activePlatform}/status`);

        setActiveSession((prev) => {
          if (!prev) return null;
          return {
            ...prev,
            status: resp.status === 'connected' ? 'connected' : prev.status,
            botResponses: resp.bot_responses,
          };
        });

        if (resp.status === 'connected') {
          // Refresh all statuses
          const s = await api<Record<string, PlatformStatus>>(
            '/web/api/v1/bridges/status',
          );
          setStatuses(s);
        }
      } catch {
        // Silently fail, will retry
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [activeSession, activePlatform]);

  async function handleConnect(platformId: string) {
    setActivePlatform(platformId);
    setActiveSession({
      platform: platformId,
      status: 'initiating',
      botResponses: [],
    });

    try {
      const resp = await api<{
        status: string;
        room_id: string;
        bot_responses: BotResponse[];
      }>(`/web/api/v1/bridges/${platformId}/login`, { method: 'POST' });

      const platform = PLATFORMS.find((p) => p.id === platformId);
      setActiveSession({
        platform: platformId,
        status:
          platform?.loginType === 'qr' ? 'waiting_qr' : 'waiting_cookies',
        botResponses: resp.bot_responses,
      });
    } catch (e) {
      setActiveSession({
        platform: platformId,
        status: 'error',
        botResponses: [],
        error: e instanceof Error ? e.message : 'Failed to initiate login',
      });
    }
  }

  async function handleSendCookies(cookies: string) {
    if (!activePlatform) return;

    setActiveSession((prev) =>
      prev ? { ...prev, status: 'polling' } : null,
    );

    try {
      const resp = await api<{
        status: string;
        bot_responses: BotResponse[];
      }>(`/web/api/v1/bridges/${activePlatform}/login/cookies`, {
        method: 'POST',
        body: JSON.stringify({ cookies }),
      });

      setActiveSession((prev) =>
        prev
          ? {
              ...prev,
              status: 'polling',
              botResponses: resp.bot_responses,
            }
          : null,
      );
    } catch (e) {
      setActiveSession((prev) =>
        prev
          ? {
              ...prev,
              status: 'error',
              error:
                e instanceof Error ? e.message : 'Failed to send cookies',
            }
          : null,
      );
    }
  }

  function handleCloseModal() {
    setActiveSession(null);
    setActivePlatform(null);
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  const platformObj = activePlatform
    ? PLATFORMS.find((p) => p.id === activePlatform)
    : null;

  return (
    <div className="min-h-screen bg-[#FAFAFA]">
      <div className="mx-auto max-w-2xl px-4 py-8">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Image
              src="/scheduled_icon.svg"
              alt="Scheduled Logo"
              width={32}
              height={32}
              className="h-8 w-8"
            />
            <h1 className="font-[family-name:var(--font-space-grotesk)] text-xl font-bold text-gray-900">
              Connections
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push('/settings')}
              className="flex cursor-pointer items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Settings
            </button>
            <button
              onClick={() => router.push('/inbox')}
              className="flex cursor-pointer items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700"
            >
              Inbox
            </button>
            <button
              onClick={() => {
                clearSession();
                window.location.href = `${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/logout`;
              }}
              className="flex cursor-pointer items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
            >
              <LogOut className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {user && (
          <p className="mb-6 text-sm text-gray-500">
            Connect your messaging accounts for{' '}
            <span className="font-medium text-gray-700">{user.email}</span>
          </p>
        )}

        {!matrixConfigured && (
          <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
            <p className="font-medium">Matrix not configured</p>
            <p className="mt-1 text-xs text-amber-600">
              Set your Matrix homeserver credentials in Settings before
              connecting chat platforms.
            </p>
          </div>
        )}

        {/* Platform list */}
        <div className="flex flex-col gap-3">
          {PLATFORMS.map((platform) => (
            <PlatformCard
              key={platform.id}
              platform={platform}
              status={statuses[platform.id]}
              onConnect={handleConnect}
            />
          ))}
        </div>
      </div>

      {/* Login modal */}
      {activeSession && platformObj && (
        <LoginModal
          platform={platformObj}
          session={activeSession}
          onClose={handleCloseModal}
          onSendCookies={handleSendCookies}
        />
      )}
    </div>
  );
}
