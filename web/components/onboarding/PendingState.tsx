'use client';

import Image from 'next/image';
import { CheckCircle, Loader2, XCircle } from 'lucide-react';

const DRAFT_AGENT_LABELS: Record<string, string> = {
  backfill: 'Syncing your calendar',
  preferences: 'Learning scheduling preferences',
  style: 'Analyzing email style',
};

const BOT_AGENT_LABELS: Record<string, string> = {
  preferences: 'Learning scheduling preferences',
};

interface PendingStateProps {
  agents: Record<string, string> | null;
  mode?: 'bot' | 'draft';
}

export default function PendingState({ agents, mode = 'draft' }: PendingStateProps) {
  const isBotMode = mode === 'bot';
  const agentLabels = isBotMode ? BOT_AGENT_LABELS : DRAFT_AGENT_LABELS;

  return (
    <>
      <div className="rounded-xl border border-gray-100 bg-[#FAFAFA] p-6">
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-purple-50">
            <Loader2 className="h-5 w-5 animate-spin text-purple-600" />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-900">
              {isBotMode
                ? 'Setting up your assistant'
                : 'Learning your style'}
            </p>
            <p className="mt-1 text-xs text-gray-500">
              {isBotMode
                ? 'Your scheduling preferences will appear here when ready.'
                : 'Your scheduling preferences and email style guide will appear here when ready.'}
            </p>
          </div>
        </div>

        {agents && (
          <div className="mt-5 space-y-3">
            {Object.entries(agentLabels).map(([key, label]) => {
              const status = agents[key];
              return (
                <div key={key} className="flex items-center gap-3">
                  {status === 'done' ? (
                    <CheckCircle className="h-4 w-4 flex-shrink-0 text-[#43614a]" />
                  ) : status === 'failed' ? (
                    <XCircle className="h-4 w-4 flex-shrink-0 text-red-400" />
                  ) : (
                    <Loader2 className="h-4 w-4 flex-shrink-0 animate-spin text-purple-400" />
                  )}
                  <span
                    className={`text-xs ${
                      status === 'done'
                        ? 'text-gray-700'
                        : status === 'failed'
                          ? 'text-red-500'
                          : 'text-gray-500'
                    }`}
                  >
                    {label}
                    {status === 'done' && ' — done'}
                    {status === 'failed' && ' — failed'}
                  </span>
                </div>
              );
            })}
          </div>
        )}

        <p className="mt-4 text-center text-xs text-gray-400">
          This typically takes a couple of minutes. You can close this tab — we&apos;ll send you an email when it&apos;s ready.
        </p>
      </div>

      <div className="mt-8 border-t border-gray-100 pt-8">
        <h2 className="mb-4 text-sm font-semibold tracking-wide text-gray-400 uppercase">
          How it works
        </h2>
        <Image
          src="/how-it-works.svg"
          alt="How Scheduled works: 1. Meeting request arrives, 2. AI drafts a reply, 3. You accept the draft, 4. Meeting is scheduled"
          width={680}
          height={620}
          className="w-full"
          priority
        />
      </div>
    </>
  );
}
