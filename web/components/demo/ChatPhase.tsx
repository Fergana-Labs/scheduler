'use client';

import { useState, useRef, useEffect } from 'react';
import { Send } from 'lucide-react';
import TypingIndicator from './TypingIndicator';
import { trackPageEvent } from '@/lib/analytics';
import type { SidePanelStep } from './SidePanel';

const API_BASE = process.env.NEXT_PUBLIC_CONTROL_PLANE_URL;

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface DemoResponse {
  reply: string;
  is_complete: boolean;
  events?: { start: string; end: string; summary: string }[];
  reasoning?: {
    summary: string;
    date_label: string;
    event_summary: string;
    agreed_time_start: string;
    agreed_time_end: string;
  };
}

interface Props {
  onStep: (step: SidePanelStep, data?: Partial<DemoResponse>) => void;
  isComplete: boolean;
}

export default function ChatPhase({ onStep, isComplete }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, isLoading]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || isLoading || isComplete) return;

    trackPageEvent('demo_message_sent');

    const userMsg: Message = { role: 'user', content: text };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput('');
    setIsLoading(true);

    // Side panel: email received → checking calendar → drafting
    onStep('received');
    await delay(600);
    onStep('checking-calendar');
    await delay(800);
    onStep('drafting');

    try {
      const res = await fetch(`${API_BASE}/api/v1/demo/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: newMessages }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Request failed');
      }

      const data: DemoResponse = await res.json();
      const assistantMsg: Message = { role: 'assistant', content: data.reply };
      const updatedMessages = [...newMessages, assistantMsg];
      setMessages(updatedMessages);

      if (data.is_complete) {
        trackPageEvent('demo_conversation_complete');
        // Show reasoning, then stop at draft-ready and wait for user to click Send
        onStep('reasoning', data);
        await delay(1200);
        onStep('draft-ready', data);
        // Don't auto-advance past here — user clicks "Send" in side panel
      } else {
        onStep('draft-ready', data);
      }
    } catch (err) {
      console.error('Demo chat error:', err);
      setMessages([
        ...newMessages,
        { role: 'assistant', content: "Sorry, I'm having trouble right now. Try again?" },
      ]);
      onStep('idle');
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Thread header */}
      <div className="mb-4 rounded-t-xl border border-gray-200 bg-white px-5 py-3">
        <div className="text-xs font-medium text-gray-400">EMAIL THREAD</div>
        <div className="mt-1 text-sm font-medium text-gray-800">
          Schedule a meeting with Sam
        </div>
      </div>

      {/* Email messages */}
      <div ref={scrollRef} className="flex-1 space-y-0 overflow-y-auto">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center rounded-b-xl border border-t-0 border-gray-200 bg-white">
            <p className="max-w-xs px-4 py-12 text-center text-sm text-gray-400">
              Type a message to start scheduling. Try something like
              &ldquo;Hey, can we grab coffee next week?&rdquo;
            </p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className="animate-fade-in border border-t-0 border-gray-200 bg-white px-5 py-4"
            style={{ animationDelay: '50ms' }}
          >
            <div className="mb-2 flex items-baseline justify-between">
              <div className="text-xs">
                <span className="font-medium text-gray-800">
                  {msg.role === 'user' ? 'You' : 'Sam'}
                </span>
                {msg.role === 'assistant' && (
                  <span className="ml-1.5 text-gray-400">&lt;sam@ferganalabs.com&gt;</span>
                )}
              </div>
              <span className="text-[10px] text-gray-300">just now</span>
            </div>
            <p className="text-sm leading-relaxed text-gray-700">{msg.content}</p>
          </div>
        ))}
        {isLoading && (
          <div className="border border-t-0 border-gray-200 bg-white px-5 py-4">
            <div className="mb-2 text-xs">
              <span className="font-medium text-gray-800">Sam</span>
              <span className="ml-1.5 text-gray-400">&lt;sam@ferganalabs.com&gt;</span>
            </div>
            <TypingIndicator align="left" />
          </div>
        )}
      </div>

      {/* Compose input */}
      <div className="mt-3 rounded-xl border border-gray-200 bg-white p-3">
        <div className="mb-2 text-xs text-gray-400">
          <span className="font-medium text-gray-500">To:</span> sam@ferganalabs.com
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isComplete ? 'Conversation complete' : 'Write your message...'}
            disabled={isLoading || isComplete}
            className="flex-1 bg-transparent text-sm text-gray-800 placeholder-gray-400 outline-none disabled:opacity-50"
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isLoading || isComplete}
            className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-[#43614a] text-white transition-all hover:bg-[#527559] disabled:opacity-40"
          >
            <Send className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <style jsx>{`
        @keyframes fade-in {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in {
          animation: fade-in 0.3s ease-out forwards;
        }
      `}</style>
    </div>
  );
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
