'use client';

import { useEffect, useState } from 'react';
import { Inbox, Calendar, FileEdit, Mail, Send, CheckCircle, Loader2 } from 'lucide-react';
import ReasoningEmail from './ReasoningEmail';

export type SidePanelStep =
  | 'idle'
  | 'received'
  | 'checking-calendar'
  | 'drafting'
  | 'reasoning'
  | 'draft-ready'
  | 'sent'
  | 'complete';

interface MaskedEvent {
  start: string;
  end: string;
  summary: string;
}

interface ReasoningData {
  summary: string;
  date_label: string;
  event_summary: string;
  agreed_time_start: string;
  agreed_time_end: string;
}

interface Props {
  step: SidePanelStep;
  events?: MaskedEvent[];
  reasoning?: ReasoningData;
  draftText?: string;
  onSendDraft?: () => void;
}

interface StepInfo {
  icon: React.ReactNode;
  title: string;
  description: string;
  active: boolean;
  complete: boolean;
}

const STEP_ORDER: SidePanelStep[] = [
  'received',
  'checking-calendar',
  'drafting',
  'reasoning',
  'draft-ready',
  'sent',
  'complete',
];

export default function SidePanel({ step, events, reasoning, draftText, onSendDraft }: Props) {
  const [visibleSteps, setVisibleSteps] = useState<SidePanelStep[]>([]);

  useEffect(() => {
    if (step === 'idle') return;
    const idx = STEP_ORDER.indexOf(step);
    if (idx >= 0) {
      setVisibleSteps(STEP_ORDER.slice(0, idx + 1));
    }
  }, [step]);

  if (step === 'idle') {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-[#43614a]/10">
            <Mail className="h-5 w-5 text-[#43614a]" />
          </div>
          <p className="text-sm text-gray-400">
            Send a message to see how
            <br />
            Scheduled works behind the scenes.
          </p>
        </div>
      </div>
    );
  }

  const steps: Record<SidePanelStep, StepInfo> = {
    idle: { icon: null, title: '', description: '', active: false, complete: false },
    received: {
      icon: <Inbox className="h-4 w-4" />,
      title: 'Email received',
      description: 'Scheduled detected a new scheduling email in Sam\'s inbox.',
      active: step === 'received',
      complete: STEP_ORDER.indexOf(step) > 0,
    },
    'checking-calendar': {
      icon: <Calendar className="h-4 w-4" />,
      title: 'Checking calendar',
      description: 'Reading Sam\'s calendar to find available time slots...',
      active: step === 'checking-calendar',
      complete: STEP_ORDER.indexOf(step) > 1,
    },
    drafting: {
      icon: <FileEdit className="h-4 w-4" />,
      title: 'Drafting reply',
      description: 'Writing a reply as Sam based on availability and preferences.',
      active: step === 'drafting',
      complete: STEP_ORDER.indexOf(step) > 2,
    },
    reasoning: {
      icon: <Mail className="h-4 w-4" />,
      title: 'Reasoning email',
      description: 'Sam gets an email explaining why this draft was created.',
      active: step === 'reasoning',
      complete: STEP_ORDER.indexOf(step) > 3,
    },
    'draft-ready': {
      icon: <Send className="h-4 w-4" />,
      title: 'Draft ready',
      description: 'The draft is waiting in Sam\'s inbox. Sam just needs to hit send.',
      active: step === 'draft-ready',
      complete: STEP_ORDER.indexOf(step) > 4,
    },
    sent: {
      icon: <CheckCircle className="h-4 w-4" />,
      title: 'Sent & invite created',
      description: 'Sam sent the reply. Scheduled automatically created a calendar invite.',
      active: step === 'sent',
      complete: STEP_ORDER.indexOf(step) > 5,
    },
    complete: {
      icon: <CheckCircle className="h-4 w-4" />,
      title: 'Meeting booked',
      description: 'The meeting is confirmed and on both calendars.',
      active: step === 'complete',
      complete: false,
    },
  };

  return (
    <div className="space-y-4">
      <div className="text-xs font-medium uppercase tracking-wider text-gray-400">
        What Scheduled is doing
      </div>

      {/* Step timeline */}
      <div className="space-y-0">
        {visibleSteps.map((s, i) => {
          const info = steps[s];
          const isLast = i === visibleSteps.length - 1;
          return (
            <div
              key={s}
              className="animate-fade-in-up flex gap-3"
              style={{ animationDelay: `${i * 50}ms` }}
            >
              {/* Timeline dot + line */}
              <div className="flex flex-col items-center">
                <div
                  className={`flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full transition-colors ${
                    info.active
                      ? 'bg-[#43614a] text-white'
                      : info.complete
                        ? 'bg-[#43614a]/15 text-[#43614a]'
                        : 'bg-gray-100 text-gray-400'
                  }`}
                >
                  {info.active && !info.complete && s !== 'complete' && s !== 'sent' ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    info.icon
                  )}
                </div>
                {!isLast && (
                  <div className="my-1 h-4 w-px bg-gray-200" />
                )}
              </div>

              {/* Step content */}
              <div className="min-w-0 pb-3">
                <div
                  className={`text-sm font-medium ${
                    info.active ? 'text-gray-900' : info.complete ? 'text-gray-600' : 'text-gray-400'
                  }`}
                >
                  {info.title}
                </div>
                <div className="mt-0.5 text-xs leading-relaxed text-gray-400">
                  {info.description}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Reasoning email card — shown when we reach that step */}
      {STEP_ORDER.indexOf(step) >= STEP_ORDER.indexOf('reasoning') && events && reasoning && (
        <div className="mt-4">
          <ReasoningEmail events={events} reasoning={reasoning} />
        </div>
      )}

      {/* Draft preview — shown when draft is ready */}
      {STEP_ORDER.indexOf(step) >= STEP_ORDER.indexOf('draft-ready') && draftText && (
        <div className="mt-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
          <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-gray-400">
            <FileEdit className="h-3.5 w-3.5" />
            Draft in Sam&apos;s inbox
          </div>
          <p className="text-sm leading-relaxed text-gray-700">{draftText}</p>
          <div className="mt-3 border-t border-dashed border-gray-200 pt-2 text-xs text-gray-400">
            Includes a scheduling link so the other person can pick a different time if needed.
          </div>
          {step === 'draft-ready' && onSendDraft && (
            <button
              onClick={onSendDraft}
              className="mt-3 inline-flex w-full items-center justify-center gap-1.5 rounded-full bg-[#43614a] px-4 py-2 text-sm font-medium text-white transition-all hover:bg-[#527559] active:scale-[0.98]"
            >
              <Send className="h-3.5 w-3.5" />
              Send as Sam
            </button>
          )}
        </div>
      )}

      <style jsx>{`
        @keyframes fade-in-up {
          from {
            opacity: 0;
            transform: translateY(8px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fade-in-up {
          animation: fade-in-up 0.4s ease-out forwards;
        }
      `}</style>
    </div>
  );
}
