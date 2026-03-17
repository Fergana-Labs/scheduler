'use client';

import { useState } from 'react';
import { api } from '@/lib/api';

interface SalesEmailToggleProps {
  initialEnabled: boolean;
}

export default function SalesEmailToggle({ initialEnabled }: SalesEmailToggleProps) {
  const [enabled, setEnabled] = useState(initialEnabled);
  const [saving, setSaving] = useState(false);

  async function toggle() {
    setSaving(true);
    try {
      await api('/web/api/v1/settings/sales-emails', {
        method: 'PUT',
        body: JSON.stringify({ enabled: !enabled }),
      });
      setEnabled(!enabled);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex items-start justify-between gap-4 rounded-xl border border-gray-100 bg-[#FAFAFA] p-4">
      <div>
        <p className="text-sm font-medium text-gray-900">Process sales emails</p>
        <p className="mt-1 text-xs text-gray-500">
          When on, Stash will draft replies to sales outreach, pitches, and
          promotional emails. When off, these are silently skipped.
        </p>
      </div>
      <button
        onClick={toggle}
        disabled={saving}
        className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
          enabled ? 'bg-[#43614a]' : 'bg-gray-200'
        } ${saving ? 'opacity-50' : ''}`}
      >
        <span
          className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-transform ${
            enabled ? 'translate-x-5' : 'translate-x-0'
          }`}
        />
      </button>
    </div>
  );
}
