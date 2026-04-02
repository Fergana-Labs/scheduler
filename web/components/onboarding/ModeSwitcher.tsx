'use client';

import { useState, useEffect, useCallback } from 'react';
import { Calendar, Mail, Loader2, ExternalLink, CheckCircle } from 'lucide-react';
import { api, getSession } from '@/lib/api';
import { track } from '@/lib/analytics';

interface ModeSwitcherProps {
  initialMode: string;
  initialGuides?: { name: string }[];
  onModeChange?: (mode: string) => void;
}

export default function ModeSwitcher({ initialMode, initialGuides, onModeChange }: ModeSwitcherProps) {
  const [mode, setMode] = useState(initialMode);
  const [switching, setSwitching] = useState(false);
  const [showConfirm, setShowConfirm] = useState<'draft' | 'bot' | null>(null);
  const [processing, setProcessing] = useState(false);
  const [processingDone, setProcessingDone] = useState(false);

  // On mount, check if we're in draft mode but missing email_style guide (post-OAuth switch)
  useEffect(() => {
    if (initialMode !== 'draft' || !initialGuides) return;
    const guideNames = new Set(initialGuides.map((g) => g.name));
    if (!guideNames.has('email_style')) {
      setProcessing(true);
    }
  }, [initialMode, initialGuides]);

  // Poll for guide completion when processing
  const pollGuides = useCallback(async () => {
    try {
      const res = await api<{ guides: { name: string }[] }>('/web/api/v1/settings');
      const guideNames = new Set(res.guides.map((g) => g.name));
      if (guideNames.has('email_style') && guideNames.has('scheduling_preferences')) {
        setProcessing(false);
        setProcessingDone(true);
        setTimeout(() => setProcessingDone(false), 3000);
      }
    } catch {
      // ignore — will retry
    }
  }, []);

  useEffect(() => {
    if (!processing) return;
    const interval = setInterval(pollGuides, 3000);
    return () => clearInterval(interval);
  }, [processing, pollGuides]);

  async function switchMode(newMode: 'draft' | 'bot') {
    setShowConfirm(null);
    setSwitching(true);
    try {
      const res = await api<{ scheduling_mode: string; needs_reauth: boolean; generating_guides?: boolean }>(
        '/web/api/v1/settings/scheduling-mode',
        {
          method: 'PUT',
          body: JSON.stringify({ mode: newMode }),
        }
      );
      if (res.needs_reauth) {
        const token = getSession() || '';
        window.location.href = `${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/google/connect?token=${token}`;
        return;
      }
      setMode(res.scheduling_mode);
      onModeChange?.(res.scheduling_mode);
      track('setting_changed', { setting: 'scheduling_mode', new_value: res.scheduling_mode });
      if (res.generating_guides) {
        setProcessing(true);
      }
    } catch {
      // revert
    } finally {
      setSwitching(false);
    }
  }

  const isBotMode = mode === 'bot';

  return (
    <div className="rounded-xl border border-gray-200 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-100">
            {isBotMode ? (
              <Calendar className="h-4 w-4 text-gray-600" />
            ) : (
              <Mail className="h-4 w-4 text-gray-600" />
            )}
          </div>
          <div>
            <p className="text-sm font-medium text-gray-900">
              {isBotMode ? 'Scheduling Assistant' : 'Draft Suggestions'}
            </p>
            <p className="text-xs text-gray-500">
              {isBotMode
                ? 'Scheduled replies as your assistant'
                : 'Scheduled drafts replies for you to send'}
            </p>
          </div>
        </div>

        {switching ? (
          <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
        ) : (
          <button
            onClick={() => setShowConfirm(isBotMode ? 'draft' : 'bot')}
            disabled={processing}
            className="flex cursor-pointer items-center gap-1 rounded-lg px-3 py-1.5 text-sm text-gray-600 transition-colors hover:bg-gray-100 disabled:cursor-default disabled:opacity-50"
          >
            Switch
            <ExternalLink className="h-3 w-3" />
          </button>
        )}
      </div>

      {/* Processing guides */}
      {processing && (
        <div className="mt-3 flex items-center gap-2 rounded-lg bg-blue-50 px-3 py-2">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-600" />
          <p className="text-xs text-blue-700">Learning your email style and preferences...</p>
        </div>
      )}

      {/* Done */}
      {processingDone && (
        <div className="mt-3 flex items-center gap-2 rounded-lg bg-green-50 px-3 py-2">
          <CheckCircle className="h-3.5 w-3.5 text-green-600" />
          <p className="text-xs text-green-700">Guides ready!</p>
        </div>
      )}

      {/* Confirmation */}
      {showConfirm && (
        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4">
          {showConfirm === 'draft' ? (
            <>
              <p className="text-sm font-medium text-gray-900">Switch to Draft Suggestions?</p>
              <p className="mt-1 text-xs text-gray-600">
                Scheduled will read your emails and draft scheduling replies. This requires Gmail access — you&apos;ll be asked to grant additional permissions.
              </p>
            </>
          ) : (
            <>
              <p className="text-sm font-medium text-gray-900">Switch to Scheduling Assistant?</p>
              <p className="mt-1 text-xs text-gray-600">
                Scheduled will act as your visible assistant. Just CC scheduling@tryscheduled.com on any thread. Only calendar access is needed.
              </p>
            </>
          )}
          <div className="mt-3 flex gap-2">
            <button
              onClick={() => switchMode(showConfirm)}
              className="cursor-pointer rounded-lg bg-[#43614a] px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-[#527559]"
            >
              Confirm
            </button>
            <button
              onClick={() => setShowConfirm(null)}
              className="cursor-pointer rounded-lg px-3 py-1.5 text-sm text-gray-600 transition-colors hover:bg-gray-100"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
