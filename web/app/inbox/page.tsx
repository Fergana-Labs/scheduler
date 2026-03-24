'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import {
  Loader2,
  LogOut,
  Check,
  X,
  Pencil,
  MessageSquare,
  ArrowLeft,
} from 'lucide-react';
import { api, captureSessionFromURL, clearSession, getSession } from '@/lib/api';

interface PendingReply {
  id: string;
  platform: string;
  room_id: string;
  sender_name: string;
  conversation_context: { sender: string; body: string }[] | null;
  proposed_reply: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
}

interface UserInfo {
  user_id: string;
  email: string;
}

const PLATFORM_LABELS: Record<string, string> = {
  whatsapp: 'WhatsApp',
  instagram: 'Instagram',
  linkedin: 'LinkedIn',
  signal: 'Signal',
  telegram: 'Telegram',
  discord: 'Discord',
  slack: 'Slack',
  matrix: 'Matrix',
};

const PLATFORM_COLORS: Record<string, string> = {
  whatsapp: 'bg-green-100 text-green-700',
  instagram: 'bg-pink-100 text-pink-700',
  linkedin: 'bg-blue-100 text-blue-700',
  signal: 'bg-indigo-100 text-indigo-700',
  telegram: 'bg-sky-100 text-sky-700',
  discord: 'bg-violet-100 text-violet-700',
  slack: 'bg-purple-100 text-purple-700',
  matrix: 'bg-gray-100 text-gray-700',
};

function timeAgo(dateString: string | null): string {
  if (!dateString) return '';
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

function PendingReplyCard({
  reply,
  onApprove,
  onDismiss,
  onEdit,
}: {
  reply: PendingReply;
  onApprove: (id: string) => void;
  onDismiss: (id: string) => void;
  onEdit: (id: string, text: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(reply.proposed_reply);
  const [loading, setLoading] = useState<'approve' | 'dismiss' | null>(null);

  const platformLabel = PLATFORM_LABELS[reply.platform] || reply.platform;
  const platformColor = PLATFORM_COLORS[reply.platform] || 'bg-gray-100 text-gray-700';

  async function handleApprove() {
    setLoading('approve');
    await onApprove(reply.id);
    setLoading(null);
  }

  async function handleDismiss() {
    setLoading('dismiss');
    await onDismiss(reply.id);
    setLoading(null);
  }

  async function handleSaveEdit() {
    await onEdit(reply.id, editText);
    setEditing(false);
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${platformColor}`}>
            {platformLabel}
          </span>
          <span className="text-sm font-medium text-gray-900">{reply.sender_name}</span>
        </div>
        <span className="text-xs text-gray-400">{timeAgo(reply.created_at)}</span>
      </div>

      {/* Conversation context */}
      {reply.conversation_context && reply.conversation_context.length > 0 && (
        <div className="mb-3 max-h-32 overflow-y-auto rounded-lg bg-gray-50 p-3">
          {reply.conversation_context.slice(-5).map((msg, i) => (
            <div key={i} className="mb-1 last:mb-0">
              <span className="text-xs font-medium text-gray-500">{msg.sender}: </span>
              <span className="text-xs text-gray-700">{msg.body}</span>
            </div>
          ))}
        </div>
      )}

      {/* Proposed reply */}
      <div className="mb-4">
        <p className="mb-1 text-xs font-medium text-gray-400">Draft reply</p>
        {editing ? (
          <div className="flex flex-col gap-2">
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              className="w-full rounded-lg border border-gray-300 p-2.5 text-sm text-gray-900 focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
              rows={3}
            />
            <div className="flex gap-2">
              <button
                onClick={handleSaveEdit}
                className="rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-800"
              >
                Save
              </button>
              <button
                onClick={() => {
                  setEditing(false);
                  setEditText(reply.proposed_reply);
                }}
                className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div
            className="cursor-pointer rounded-lg bg-blue-50 p-3 text-sm text-gray-900 transition-colors hover:bg-blue-100"
            onClick={() => setEditing(true)}
          >
            {reply.proposed_reply}
            <Pencil className="ml-1 inline-block h-3 w-3 text-gray-400" />
          </div>
        )}
      </div>

      {/* Actions */}
      {!editing && (
        <div className="flex gap-2">
          <button
            onClick={handleApprove}
            disabled={!!loading}
            className="flex flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-800 disabled:opacity-50"
          >
            {loading === 'approve' ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Check className="h-4 w-4" />
            )}
            Send
          </button>
          <button
            onClick={handleDismiss}
            disabled={!!loading}
            className="flex cursor-pointer items-center justify-center gap-1.5 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-50"
          >
            {loading === 'dismiss' ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <X className="h-4 w-4" />
            )}
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
}

export default function InboxPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserInfo | null>(null);
  const [replies, setReplies] = useState<PendingReply[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchReplies = useCallback(async () => {
    try {
      const data = await api<PendingReply[]>('/web/api/v1/chat/pending');
      setReplies(data);
    } catch {
      // silently fail — will retry on next poll
    }
  }, []);

  useEffect(() => {
    captureSessionFromURL();
    async function init() {
      try {
        const userInfo = await api<UserInfo>('/auth/me');
        setUser(userInfo);
        await fetchReplies();
      } catch {
        clearSession();
        window.location.href = `${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/login`;
        return;
      } finally {
        setLoading(false);
      }
    }
    init();
  }, [fetchReplies]);

  // Poll for new replies every 30s
  useEffect(() => {
    if (!user) return;
    const interval = setInterval(fetchReplies, 30000);
    return () => clearInterval(interval);
  }, [user, fetchReplies]);

  async function handleApprove(id: string) {
    try {
      await api(`/web/api/v1/chat/pending/${id}/approve`, { method: 'POST' });
      setReplies((prev) => prev.filter((r) => r.id !== id));
    } catch (e) {
      console.error('Failed to approve reply:', e);
    }
  }

  async function handleDismiss(id: string) {
    try {
      await api(`/web/api/v1/chat/pending/${id}/dismiss`, { method: 'POST' });
      setReplies((prev) => prev.filter((r) => r.id !== id));
    } catch (e) {
      console.error('Failed to dismiss reply:', e);
    }
  }

  async function handleEdit(id: string, text: string) {
    try {
      await api(`/web/api/v1/chat/pending/${id}`, {
        method: 'PUT',
        body: JSON.stringify({ proposed_reply: text }),
      });
      setReplies((prev) =>
        prev.map((r) => (r.id === id ? { ...r, proposed_reply: text } : r)),
      );
    } catch (e) {
      console.error('Failed to edit reply:', e);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

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
              Chat Inbox
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
            Pending chat replies for{' '}
            <span className="font-medium text-gray-700">{user.email}</span>
          </p>
        )}

        {/* Reply list */}
        {replies.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-gray-300 bg-white py-16">
            <MessageSquare className="mb-3 h-10 w-10 text-gray-300" />
            <p className="text-sm font-medium text-gray-500">No pending replies</p>
            <p className="mt-1 text-xs text-gray-400">
              Scheduling messages from your chats will appear here for review.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {replies.map((reply) => (
              <PendingReplyCard
                key={reply.id}
                reply={reply}
                onApprove={handleApprove}
                onDismiss={handleDismiss}
                onEdit={handleEdit}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
