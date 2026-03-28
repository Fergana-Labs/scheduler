'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Send } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import TypingIndicator from './TypingIndicator';
import CalendarDayView from './CalendarDayView';
import MeetingConfirmed from './MeetingConfirmed';
import { trackPageEvent } from '@/lib/analytics';
import type { SidePanelStep } from './SidePanel';

const API_BASE = process.env.NEXT_PUBLIC_CONTROL_PLANE_URL;

interface MaskedEvent {
  start: string;
  end: string;
  summary: string;
}

interface ReasoningData {
  summary: string;
  date_label: string;
}

export interface DemoResponse {
  reply: string;
  is_complete: boolean;
  events?: MaskedEvent[];
  proposed_slots?: { start: string; end: string }[];
  reasoning?: ReasoningData;
  event_summary?: string;
  agreed_time_start?: string;
  agreed_time_end?: string;
}

type MessageType = 'user' | 'assistant' | 'reasoning' | 'confirmation';

interface Message {
  type: MessageType;
  content: string;
  isDraft?: boolean;
  events?: MaskedEvent[];
  proposedSlots?: { start: string; end: string }[];
  reasoning?: ReasoningData;
  eventSummary?: string;
  agreedTimeStart?: string;
  agreedTimeEnd?: string;
}

interface Props {
  onStep: (step: SidePanelStep, data?: Partial<DemoResponse>) => void;
  onDraftReady: (data: DemoResponse) => void;
  onSendDraft: () => void;
  draftSent: boolean;
  isComplete: boolean;
  autopilot: boolean;
}

export default function ChatPhase({ onStep, onDraftReady, onSendDraft, draftSent, isComplete, autopilot }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [waitingForSend, setWaitingForSend] = useState(false);
  const [highlightCompose, setHighlightCompose] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const exchangeRef = useRef(0);
  const latestResponseRef = useRef<DemoResponse | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, isLoading]);

  // Handle draft sent (manual or autopilot)
  useEffect(() => {
    if (draftSent && waitingForSend) {
      setMessages((prev) =>
        prev.map((m) => (m.isDraft ? { ...m, isDraft: false } : m)),
      );
      setWaitingForSend(false);

      // If conversation is complete, insert confirmation card
      const resp = latestResponseRef.current;
      if (resp?.is_complete && resp.agreed_time_start && resp.agreed_time_end) {
        setTimeout(() => {
          setMessages((prev) => [
            ...prev,
            {
              type: 'confirmation',
              content: '',
              eventSummary: resp.event_summary || 'Meeting',
              agreedTimeStart: resp.agreed_time_start,
              agreedTimeEnd: resp.agreed_time_end,
            },
          ]);
        }, 800);
      } else {
        // Highlight compose area to guide user — stays until they type
        setHighlightCompose(true);
        textareaRef.current?.focus();
      }
    }
  }, [draftSent, waitingForSend]);

  // Autopilot: auto-send after 1.5s
  useEffect(() => {
    if (autopilot && waitingForSend && !draftSent) {
      const timer = setTimeout(() => {
        onStep('sent');
        setMessages((prev) =>
          prev.map((m) => (m.isDraft ? { ...m, isDraft: false } : m)),
        );
        setWaitingForSend(false);

        const resp = latestResponseRef.current;
        if (resp?.is_complete && resp.agreed_time_start && resp.agreed_time_end) {
          setTimeout(() => {
            onStep('complete');
            setMessages((prev) => [
              ...prev,
              {
                type: 'confirmation',
                content: '',
                eventSummary: resp.event_summary || 'Meeting',
                agreedTimeStart: resp.agreed_time_start,
                agreedTimeEnd: resp.agreed_time_end,
              },
            ]);
          }, 800);
        } else {
          // Highlight compose area — stays until they type
          setHighlightCompose(true);
          textareaRef.current?.focus();
        }
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [autopilot, waitingForSend, draftSent, onStep]);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || isLoading || isComplete || waitingForSend) return;

    trackPageEvent('demo_message_sent');

    const userMsg: Message = { type: 'user', content: text };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput('');
    setIsLoading(true);

    onStep('received');
    await delay(600);
    onStep('checking-calendar');
    await delay(800);
    onStep('drafting');

    try {
      const apiMessages = newMessages
        .filter((m) => m.type === 'user' || m.type === 'assistant')
        .map((m) => ({ role: m.type === 'user' ? 'user' : 'assistant', content: m.content }));

      const res = await fetch(`${API_BASE}/api/v1/demo/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: apiMessages }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Request failed');
      }

      const data: DemoResponse = await res.json();
      latestResponseRef.current = data;
      exchangeRef.current += 1;

      const newMsgs: Message[] = [];

      // First exchange: insert reasoning email before the draft
      if (exchangeRef.current === 1 && data.events && data.reasoning) {
        newMsgs.push({
          type: 'reasoning',
          content: data.reasoning.summary,
          events: data.events,
          proposedSlots: data.proposed_slots,
          reasoning: data.reasoning,
        });
      }

      newMsgs.push({
        type: 'assistant',
        content: data.reply,
        isDraft: true,
      });

      setMessages((prev) => [...prev, ...newMsgs]);
      setWaitingForSend(true);

      if (data.is_complete) {
        trackPageEvent('demo_conversation_complete');
        onStep('reasoning', data);
        await delay(1000);
      }

      onStep('draft-ready', data);
      onDraftReady(data);
    } catch (err) {
      console.error('Demo chat error:', err);
      setMessages((prev) => [
        ...prev,
        { type: 'assistant', content: "Sorry, I'm having trouble right now. Try again?" },
      ]);
      onStep('idle');
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, isComplete, waitingForSend, messages, onStep, onDraftReady, autopilot]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const hasMessages = messages.length > 0;

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-gray-200 bg-white">
      {/* Thread header */}
      <div className="border-b border-gray-200 px-5 py-3">
        <div className="text-sm font-semibold text-gray-900">
          Scheduled Demo Request
        </div>
        <div className="mt-0.5 text-xs text-gray-400">
          To: sam@ferganalabs.com
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {!hasMessages && !isLoading && (
          <div className="flex h-full items-center justify-center px-6">
            <p className="max-w-xs text-center text-sm leading-relaxed text-gray-400">
              Send a message like you&apos;re trying to schedule a virtual meeting.
              Watch how Scheduled handles it behind the scenes.
            </p>
          </div>
        )}

        {messages.map((msg, i) => {
          if (msg.type === 'reasoning') {
            return (
              <div key={i} className="border-b border-gray-100 border-l-2 border-l-[#43614a] bg-[#43614a]/[0.03] px-5 py-4">
                <div className="flex items-center gap-2 text-xs">
                  <span className="rounded bg-[#43614a]/10 px-1.5 py-0.5 text-[10px] font-semibold text-[#43614a]">
                    INTERNAL
                  </span>
                  <span className="font-medium text-gray-600">Scheduled</span>
                  <span className="text-gray-400">&lt;internal@tryscheduled.com&gt;</span>
                </div>
                <div className="mt-3 text-sm leading-relaxed text-gray-600">
                  <p className="font-medium text-gray-700">Scheduled drafted a reply in this thread.</p>
                  <p className="mt-2 text-xs leading-relaxed text-gray-500">
                    <span className="font-medium text-gray-600">Reasoning:</span> {msg.content}
                  </p>
                </div>
                {msg.events && msg.reasoning && (
                  <CalendarDayView
                    events={msg.events}
                    proposedTimes={msg.proposedSlots}
                    dateLabel={msg.reasoning.date_label}
                  />
                )}
              </div>
            );
          }

          if (msg.type === 'confirmation') {
            return (
              <div key={i} className="border-b border-gray-100">
                <MeetingConfirmed
                  eventSummary={msg.eventSummary || 'Meeting'}
                  agreedTimeStart={msg.agreedTimeStart || ''}
                  agreedTimeEnd={msg.agreedTimeEnd || ''}
                />
              </div>
            );
          }

          // user or assistant — render markdown
          return (
            <div
              key={i}
              className={`border-b border-gray-100 px-5 py-4 ${
                msg.isDraft ? 'bg-amber-50/40' : ''
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs">
                  <span className="font-semibold text-gray-900">
                    {msg.type === 'user' ? 'You' : 'Sam'}
                  </span>
                  {msg.type === 'assistant' && (
                    <span className="text-gray-400">&lt;sam@ferganalabs.com&gt;</span>
                  )}
                  {msg.isDraft && (
                    <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-600">
                      DRAFT
                    </span>
                  )}
                </div>
                <span className="text-[10px] text-gray-300">just now</span>
              </div>
              <div className="mt-2 text-sm leading-relaxed text-gray-700 [&_ul]:ml-4 [&_ul]:list-disc [&_ul]:space-y-0.5 [&_ol]:ml-4 [&_ol]:list-decimal [&_ol]:space-y-0.5 [&_p]:mb-1 [&_p:last-child]:mb-0">
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              </div>
              {msg.isDraft && !autopilot && (
                <button
                  onClick={onSendDraft}
                  className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-[#43614a] px-4 py-2 text-xs font-medium text-white transition-all hover:bg-[#527559] active:scale-[0.98]"
                >
                  <Send className="h-3 w-3" />
                  Send draft from Sam
                </button>
              )}
            </div>
          );
        })}

        {isLoading && (
          <div className="border-b border-gray-100 px-5 py-4">
            <div className="flex items-center gap-2 text-xs">
              <span className="font-semibold text-gray-900">Sam</span>
              <span className="text-gray-400">&lt;sam@ferganalabs.com&gt;</span>
            </div>
            <div className="mt-2">
              <TypingIndicator align="left" />
            </div>
          </div>
        )}
      </div>

      {/* Compose area — hidden when meeting is confirmed */}
      {!isComplete ? (
        <div
          className={`border-t px-5 py-3 transition-colors duration-500 ${
            highlightCompose
              ? 'border-[#43614a] bg-[#43614a]/[0.03]'
              : 'border-gray-200'
          }`}
        >
          {highlightCompose && (
            <div className="mb-2 text-xs font-medium text-[#43614a]">
              Your turn — reply to continue the conversation
            </div>
          )}
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => { setInput(e.target.value); setHighlightCompose(false); }}
            onKeyDown={handleKeyDown}
            placeholder={
              waitingForSend && !autopilot
                ? 'Hit "Send draft" in the panel first'
                : hasMessages
                  ? 'Reply to Sam...'
                  : 'Hey, I\'d love to set up a meeting to learn more about Scheduled...'
            }
            disabled={isLoading || (waitingForSend && !autopilot)}
            rows={2}
            className="w-full resize-none bg-transparent text-sm leading-relaxed text-gray-800 placeholder-gray-400 outline-none disabled:opacity-50"
          />
          <div className="flex items-center justify-between pt-1">
            <span className="text-[11px] text-gray-400">
              To: sam@ferganalabs.com
            </span>
            <button
              onClick={sendMessage}
              disabled={!input.trim() || isLoading || (waitingForSend && !autopilot)}
              className="inline-flex items-center gap-1.5 rounded bg-[#43614a] px-3 py-1 text-xs font-medium text-white transition-all hover:bg-[#527559] disabled:opacity-40"
            >
              <Send className="h-3 w-3" />
              Send
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
