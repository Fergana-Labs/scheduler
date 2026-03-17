'use client';

import { useState } from 'react';
import { api } from '@/lib/api';

interface DisconnectButtonProps {
  onDisconnected: () => void;
}

export default function DisconnectButton({ onDisconnected }: DisconnectButtonProps) {
  const [confirming, setConfirming] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  async function handleDisconnect() {
    setDisconnecting(true);
    try {
      await api('/web/api/v1/account/disconnect', { method: 'POST' });
      setConfirming(false);
      onDisconnected();
    } catch {
      setDisconnecting(false);
      setConfirming(false);
    }
  }

  return (
    <>
      <button
        onClick={() => setConfirming(true)}
        className="w-full rounded-xl border border-red-200 bg-white px-4 py-3 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
      >
        Disconnect Google Account
      </button>

      {confirming && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="mx-4 w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-base font-semibold text-gray-900">
              Disconnect your account?
            </h3>
            <p className="mt-2 text-sm text-gray-500">
              This will revoke Stash&apos;s access to your Google account. You
              can reconnect at any time.
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setConfirming(false)}
                disabled={disconnecting}
                className="rounded-lg px-4 py-2 text-sm text-gray-500 hover:bg-gray-100"
              >
                Cancel
              </button>
              <button
                onClick={handleDisconnect}
                disabled={disconnecting}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                {disconnecting ? 'Disconnecting...' : 'Disconnect'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
