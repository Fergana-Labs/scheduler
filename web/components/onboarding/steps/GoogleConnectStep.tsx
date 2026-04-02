'use client';

import { Calendar, Mail, Shield } from 'lucide-react';
import { getSession } from '@/lib/api';

interface GoogleConnectStepProps {
  email: string;
  mode: 'bot' | 'draft';
}

export default function GoogleConnectStep({ email, mode }: GoogleConnectStepProps) {
  const token = getSession() || '';
  const connectUrl = mode === 'bot'
    ? `${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/google/connect-calendar?token=${token}`
    : `${process.env.NEXT_PUBLIC_CONTROL_PLANE_URL}/auth/google/connect?token=${token}`;

  return (
    <div>
      <h1 className="text-xl font-semibold text-gray-900">
        {mode === 'bot' ? 'Connect your calendar' : 'Connect your Google account'}
      </h1>
      <p className="mt-2 text-sm text-gray-500">
        Signed in as{' '}
        <span className="font-medium text-gray-700">{email}</span>
      </p>

      <div className="mt-6 rounded-xl border border-gray-200 bg-gray-50 p-4">
        <p className="text-sm font-medium text-gray-700 mb-3">
          {mode === 'bot' ? 'Scheduled will request:' : 'Scheduled will request access to:'}
        </p>
        <ul className="space-y-2.5">
          {mode === 'bot' ? (
            <>
              <li className="flex items-center gap-2.5 text-sm text-gray-600">
                <Calendar className="h-4 w-4 text-[#43614a]" />
                Read your calendar to check availability
              </li>
              <li className="flex items-center gap-2.5 text-sm text-gray-600">
                <Shield className="h-4 w-4 text-[#43614a]" />
                No email access — your inbox stays completely private
              </li>
            </>
          ) : (
            <>
              <li className="flex items-center gap-2.5 text-sm text-gray-600">
                <Mail className="h-4 w-4 text-[#43614a]" />
                Read emails to detect scheduling conversations
              </li>
              <li className="flex items-center gap-2.5 text-sm text-gray-600">
                <Mail className="h-4 w-4 text-[#43614a]" />
                Create draft replies for you to review
              </li>
              <li className="flex items-center gap-2.5 text-sm text-gray-600">
                <Calendar className="h-4 w-4 text-[#43614a]" />
                Read and write to your calendar
              </li>
            </>
          )}
        </ul>
      </div>

      <a
        href={connectUrl}
        className="mt-6 inline-flex w-full items-center justify-center rounded-xl bg-[#43614a] px-6 py-4 text-base font-semibold text-white transition-colors hover:bg-[#527559]"
      >
        {mode === 'bot' ? 'Connect Calendar' : 'Connect Google Account'}
      </a>
    </div>
  );
}
