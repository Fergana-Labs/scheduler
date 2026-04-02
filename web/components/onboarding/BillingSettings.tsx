'use client';

import { useEffect, useState } from 'react';
import { CreditCard, Loader2, ExternalLink } from 'lucide-react';
import { api } from '@/lib/api';

interface BillingStatus {
  subscription_status: string;
  trial_ends_at: string | null;
  current_period_end: string | null;
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  trialing: { label: 'Free Trial', color: 'bg-blue-100 text-blue-700' },
  active: { label: 'Active', color: 'bg-green-100 text-green-700' },
  past_due: { label: 'Past Due', color: 'bg-red-100 text-red-700' },
  canceled: { label: 'Canceled', color: 'bg-gray-100 text-gray-600' },
  none: { label: 'No Plan', color: 'bg-gray-100 text-gray-600' },
};

export default function BillingSettings() {
  const [status, setStatus] = useState<BillingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [portalLoading, setPortalLoading] = useState(false);

  useEffect(() => {
    api<BillingStatus>('/web/api/v1/billing/status')
      .then(setStatus)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleManage() {
    setPortalLoading(true);
    try {
      const res = await api<{ portal_url: string }>('/web/api/v1/billing/portal', {
        method: 'POST',
      });
      window.location.href = res.portal_url;
    } catch {
      setPortalLoading(false);
    }
  }

  if (loading || !status) {
    return (
      <div className="rounded-xl border border-gray-200 p-4">
        <div className="flex items-center gap-3">
          <CreditCard className="h-4 w-4 text-gray-400" />
          <span className="text-sm text-gray-400">Loading billing...</span>
        </div>
      </div>
    );
  }

  const statusInfo = STATUS_LABELS[status.subscription_status] || STATUS_LABELS.none;

  function formatDate(iso: string | null) {
    if (!iso) return null;
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }

  return (
    <div className="rounded-xl border border-gray-200 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-100">
            <CreditCard className="h-4 w-4 text-gray-600" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-900">Billing</span>
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusInfo.color}`}>
                {statusInfo.label}
              </span>
            </div>
            {status.subscription_status === 'trialing' && status.trial_ends_at && (
              <p className="text-xs text-gray-500">Trial ends {formatDate(status.trial_ends_at)}</p>
            )}
            {status.subscription_status === 'active' && status.current_period_end && (
              <p className="text-xs text-gray-500">Next billing {formatDate(status.current_period_end)}</p>
            )}
            {status.subscription_status === 'past_due' && (
              <p className="text-xs text-red-600">Payment failed — please update your card</p>
            )}
          </div>
        </div>

        <button
          onClick={handleManage}
          disabled={portalLoading || status.subscription_status === 'none'}
          className="flex cursor-pointer items-center gap-1 rounded-lg px-3 py-1.5 text-sm text-gray-600 transition-colors hover:bg-gray-100 disabled:cursor-default disabled:opacity-50"
        >
          {portalLoading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <>
              Manage
              <ExternalLink className="h-3 w-3" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
