'use client';

import { getSession } from '@/lib/api';

export default function DisconnectedState() {
  const connectUrl = `${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/google/connect?token=${getSession() || ''}`;

  return (
    <div className="rounded-2xl border border-dashed border-gray-300 bg-gray-50 px-6 py-12 text-center">
      <h2 className="text-2xl font-semibold text-gray-900">
        Your Google account has been disconnected.
      </h2>
      <p className="mt-3 text-sm text-gray-600">
        Reconnect to resume using Scheduled.
      </p>
      <a
        href={connectUrl}
        className="mt-8 inline-flex w-full items-center justify-center rounded-xl bg-[#43614a] px-6 py-4 text-base font-semibold text-white transition-colors hover:bg-[#527559]"
      >
        Reconnect with Google
      </a>
    </div>
  );
}
