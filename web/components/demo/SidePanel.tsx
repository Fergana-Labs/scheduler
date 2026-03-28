'use client';

import { useEffect, useState, useRef } from 'react';
import { Inbox, Calendar, FileEdit, Mail, Send, CheckCircle, Loader2, CalendarCheck, Zap } from 'lucide-react';

export type SidePanelStep =
  | 'idle'
  | 'received'
  | 'checking-calendar'
  | 'drafting'
  | 'reasoning'
  | 'draft-ready'
  | 'sent'
  | 'complete';

interface Props {
  step: SidePanelStep;
  autopilot?: boolean;
}

interface StepEntry {
  step: SidePanelStep;
  round: number;
  key: string;
}

const STEP_META: Record<SidePanelStep, { icon: React.ReactNode; title: string; description: string; autopilotDesc?: string }> = {
  idle: { icon: null, title: '', description: '' },
  received: {
    icon: <Inbox className="h-4 w-4" />,
    title: 'Email received',
    description: 'Scheduled detected a new scheduling email.',
  },
  'checking-calendar': {
    icon: <Calendar className="h-4 w-4" />,
    title: 'Checking calendar',
    description: 'Reading Sam\'s calendar for available slots...',
  },
  drafting: {
    icon: <FileEdit className="h-4 w-4" />,
    title: 'Drafting reply',
    description: 'Writing a reply as Sam.',
  },
  reasoning: {
    icon: <Mail className="h-4 w-4" />,
    title: 'Reasoning email sent',
    description: 'Sam gets an internal email explaining the draft.',
  },
  'draft-ready': {
    icon: <Send className="h-4 w-4" />,
    title: 'Draft ready',
    description: 'Waiting for Sam to hit send.',
    autopilotDesc: 'Auto-sending...',
  },
  sent: {
    icon: <CheckCircle className="h-4 w-4" />,
    title: 'Reply sent',
    description: 'Sam sent the reply.',
  },
  complete: {
    icon: <CalendarCheck className="h-4 w-4" />,
    title: 'Invite sent',
    description: 'Calendar invite created for both parties.',
  },
};

const SPINNER_STEPS: SidePanelStep[] = ['received', 'checking-calendar', 'drafting', 'draft-ready'];

export default function SidePanel({ step, autopilot }: Props) {
  const [entries, setEntries] = useState<StepEntry[]>([]);
  const roundRef = useRef(0);

  useEffect(() => {
    if (step === 'idle') return;

    // New round starts when 'received' fires
    if (step === 'received') {
      roundRef.current += 1;
    }

    const round = roundRef.current;
    const key = `${step}-${round}`;

    setEntries((prev) => {
      if (prev.some((e) => e.key === key)) return prev;
      return [...prev, { step, round, key }];
    });
  }, [step]);

  if (entries.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-[#43614a]/10">
            <Mail className="h-5 w-5 text-[#43614a]" />
          </div>
          <p className="text-xs text-gray-400">
            Waiting for first message...
          </p>
        </div>
      </div>
    );
  }

  const lastEntry = entries[entries.length - 1];

  return (
    <div className="space-y-5">
      <div className="text-xs font-medium uppercase tracking-wider text-gray-400">
        What Scheduled is doing
      </div>

      {/* Full accumulated timeline */}
      <div className="space-y-1">
        {entries.map((entry, i) => {
          const meta = STEP_META[entry.step];
          if (!meta.icon) return null;

          const isLast = i === entries.length - 1;
          const isActive = isLast && step === entry.step;
          const isComplete = !isLast;
          const showSpinner = isActive && SPINNER_STEPS.includes(entry.step);

          const description = autopilot && entry.step === 'draft-ready'
            ? (meta.autopilotDesc || meta.description)
            : meta.description;

          return (
            <div key={entry.key} className="flex gap-3">
              <div className="flex flex-col items-center">
                <div
                  className={`flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full transition-colors ${
                    isActive
                      ? 'bg-[#43614a] text-white'
                      : isComplete
                        ? 'bg-[#43614a]/15 text-[#43614a]'
                        : 'bg-gray-100 text-gray-400'
                  }`}
                >
                  {showSpinner ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    meta.icon
                  )}
                </div>
                {!isLast && <div className="my-1 h-5 w-px bg-gray-200" />}
              </div>
              <div className="min-w-0 pb-2 pt-0.5">
                <div
                  className={`text-sm font-medium ${
                    isActive ? 'text-gray-900' : isComplete ? 'text-gray-600' : 'text-gray-400'
                  }`}
                >
                  {meta.title}
                </div>
                <div className="mt-0.5 text-xs leading-relaxed text-gray-400">
                  {description}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Autopilot callout — shown after first reply is sent */}
      {autopilot && step === 'sent' && (
        <div className="flex items-start gap-2 rounded-lg bg-[#43614a]/5 px-3 py-2.5">
          <Zap className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-[#43614a]" />
          <div className="text-xs leading-relaxed text-gray-600">
            <span className="font-medium text-[#43614a]">Autopilot enabled.</span>{' '}
            Scheduled will automatically send replies as they&apos;re drafted.
          </div>
        </div>
      )}

      {/* Send draft button moved to ChatPhase — sidebar is status-only */}
    </div>
  );
}
