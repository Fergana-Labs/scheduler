'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Maximize2, X, Pencil, Eye, RefreshCw, Info } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { api } from '@/lib/api';
import { track } from '@/lib/analytics';

interface GuideEditorProps {
  name: string;
  label: string;
  initialContent: string;
  updatedAt: string;
  isDefault?: boolean;
}

const mdComponents = {
  h1: ({ children, ...props }: React.ComponentPropsWithoutRef<'h1'>) => (
    <h1 className="text-base font-semibold text-gray-900 mb-2" {...props}>{children}</h1>
  ),
  h2: ({ children, ...props }: React.ComponentPropsWithoutRef<'h2'>) => (
    <h2 className="text-sm font-semibold text-gray-900 mb-2" {...props}>{children}</h2>
  ),
  h3: ({ children, ...props }: React.ComponentPropsWithoutRef<'h3'>) => (
    <h3 className="text-sm font-medium text-gray-900 mb-1" {...props}>{children}</h3>
  ),
  p: ({ children, ...props }: React.ComponentPropsWithoutRef<'p'>) => (
    <p className="text-sm text-gray-600 mb-2 leading-relaxed" {...props}>{children}</p>
  ),
  ul: ({ children, ...props }: React.ComponentPropsWithoutRef<'ul'>) => (
    <ul className="text-sm text-gray-600 list-disc pl-5 mb-2 space-y-1" {...props}>{children}</ul>
  ),
  ol: ({ children, ...props }: React.ComponentPropsWithoutRef<'ol'>) => (
    <ol className="text-sm text-gray-600 list-decimal pl-5 mb-2 space-y-1" {...props}>{children}</ol>
  ),
  strong: ({ children, ...props }: React.ComponentPropsWithoutRef<'strong'>) => (
    <strong className="font-semibold text-gray-800" {...props}>{children}</strong>
  ),
  code: ({ children, ...props }: React.ComponentPropsWithoutRef<'code'>) => (
    <code className="text-xs bg-gray-100 rounded px-1 py-0.5 font-mono" {...props}>{children}</code>
  ),
};


export default function GuideEditor({ name, label, initialContent, updatedAt, isDefault }: GuideEditorProps) {
  const [content, setContent] = useState(initialContent);
  const [draft, setDraft] = useState(initialContent);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [regenerating, setRegenerating] = useState(false);
  const [lastUpdatedAt, setLastUpdatedAt] = useState(updatedAt);
  const [showingDefault, setShowingDefault] = useState(isDefault ?? false);

  const lastSavedRef = useRef(initialContent);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const savedFadeRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const flushSave = useCallback(async () => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
    // Read latest draft from ref-backed state
    const currentDraft = draftRef.current;
    if (currentDraft === lastSavedRef.current) return;

    setSaveStatus('saving');
    try {
      await api(`/web/api/v1/guides/${encodeURIComponent(name)}`, {
        method: 'PUT',
        body: JSON.stringify({ content: currentDraft }),
      });
      lastSavedRef.current = currentDraft;
      setContent(currentDraft);
      setSaveStatus('saved');
      track('guide_edited', { guide_name: name });
      if (savedFadeRef.current) clearTimeout(savedFadeRef.current);
      savedFadeRef.current = setTimeout(() => setSaveStatus('idle'), 2000);
    } catch {
      setSaveStatus('idle');
    }
  }, [name]);

  // Keep a ref of draft so flushSave always reads latest
  const draftRef = useRef(draft);
  useEffect(() => {
    draftRef.current = draft;
  }, [draft]);

  function scheduleSave(newDraft: string) {
    setDraft(newDraft);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      flushSave();
    }, 1000);
  }

  function closeModal() {
    flushSave();
    setModalOpen(false);
    setEditing(false);
  }

  // Escape key closes modal
  useEffect(() => {
    if (!modalOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') closeModal();
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  });

  // Lock body scroll when modal open
  useEffect(() => {
    if (modalOpen) {
      document.body.style.overflow = 'hidden';
      return () => { document.body.style.overflow = ''; };
    }
  }, [modalOpen]);

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (savedFadeRef.current) clearTimeout(savedFadeRef.current);
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  async function handleRegenerate() {
    setRegenerating(true);
    setEditing(false);
    try {
      await api(`/web/api/v1/guides/${encodeURIComponent(name)}/regenerate`, {
        method: 'POST',
      });
    } catch {
      setRegenerating(false);
      return;
    }

    // Poll for updated content
    const startTime = Date.now();
    pollRef.current = setInterval(async () => {
      if (Date.now() - startTime > 3 * 60 * 1000) {
        // Timeout after 3 minutes
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = null;
        setRegenerating(false);
        return;
      }
      try {
        const data = await api<{
          guides: { name: string; content: string; updated_at: string; is_default?: boolean }[];
        }>('/web/api/v1/settings');
        const guide = data.guides.find((g: { name: string }) => g.name === name);
        if (guide && guide.updated_at !== lastUpdatedAt) {
          setContent(guide.content);
          setDraft(guide.content);
          lastSavedRef.current = guide.content;
          draftRef.current = guide.content;
          setLastUpdatedAt(guide.updated_at);
          setShowingDefault(guide.is_default ?? false);
          setRegenerating(false);
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch {
        // ignore polling errors
      }
    }, 5000);
  }

  return (
    <>
      {/* Card view (truncated) */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => setModalOpen(true)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setModalOpen(true); } }}
        className="group relative w-full cursor-pointer overflow-hidden rounded-xl border border-gray-100 bg-[#FAFAFA] p-4 text-left transition-colors hover:border-gray-200"
        style={{ maxHeight: '10rem' }}
      >
        <div className="mb-2 flex items-center justify-between">
          <p className="text-sm font-medium text-gray-900">{label}</p>
          <Maximize2 className="h-3.5 w-3.5 text-gray-400 opacity-0 transition-opacity group-hover:opacity-100" />
        </div>
        {showingDefault && (
          <div className="mb-2 flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
            <p className="text-xs text-amber-800">
              Using generic defaults — click to regenerate from your emails or edit directly.
            </p>
          </div>
        )}
        <div className="relative overflow-hidden" style={{ maxHeight: '5.5rem' }}>
          <ReactMarkdown components={mdComponents}>{content}</ReactMarkdown>
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-[#FAFAFA]" />
        </div>
      </div>

      {/* Modal */}
      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={(e) => { if (e.target === e.currentTarget) closeModal(); }}
        >
          <div className="mx-4 flex max-h-[85vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-xl">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
              <div className="flex items-center gap-3">
                <h2 className="text-base font-semibold text-gray-900">{label}</h2>
                {saveStatus === 'saving' && (
                  <span className="text-xs text-gray-400">Saving...</span>
                )}
                {saveStatus === 'saved' && (
                  <span className="text-xs text-green-600">Saved</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleRegenerate}
                  disabled={regenerating}
                  className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-gray-500 transition-colors hover:bg-gray-100 disabled:opacity-50"
                  title="Regenerate"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${regenerating ? 'animate-spin' : ''}`} />
                  Regenerate
                </button>
                <button
                  onClick={() => setEditing(!editing)}
                  disabled={regenerating}
                  className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-gray-500 transition-colors hover:bg-gray-100 disabled:opacity-50"
                  title={editing ? 'View' : 'Edit'}
                >
                  {editing ? (
                    <><Eye className="h-3.5 w-3.5" /> View</>
                  ) : (
                    <><Pencil className="h-3.5 w-3.5" /> Edit</>
                  )}
                </button>
                <button
                  onClick={closeModal}
                  className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Body */}
            <div className="relative flex-1 overflow-y-auto px-6 py-4">
              {showingDefault && !regenerating && (
                <div className="mb-4 flex items-start gap-2.5 rounded-lg bg-amber-50 border border-amber-200 px-4 py-3">
                  <Info className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                  <div className="text-sm text-amber-800">
                    <p className="font-medium">Using generic defaults</p>
                    <p className="mt-0.5 text-xs text-amber-700">
                      We couldn&apos;t learn your style from your emails yet. Try <button onClick={handleRegenerate} className="underline font-medium hover:text-amber-900">regenerating</button> once you have more scheduling history, or edit the defaults directly to match your preferences.
                    </p>
                  </div>
                </div>
              )}
              {regenerating && (
                <div className="absolute inset-0 z-10 flex items-center justify-center rounded-b-2xl bg-white/80">
                  <RefreshCw className="h-6 w-6 animate-spin text-gray-400" />
                </div>
              )}
              {editing ? (
                <textarea
                  value={draft}
                  onChange={(e) => scheduleSave(e.target.value)}
                  className="h-full min-h-[400px] w-full resize-none rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-700 font-mono leading-relaxed focus:border-[#43614a] focus:outline-none focus:ring-1 focus:ring-[#43614a]"
                />
              ) : (
                <ReactMarkdown components={mdComponents}>{content}</ReactMarkdown>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
