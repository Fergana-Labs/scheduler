'use client';

import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import Image from 'next/image';

function PermissionsContent() {
  const searchParams = useSearchParams();
  const retryUrl = searchParams.get('retry_url');

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white p-8 shadow-lg">
        <div className="mb-6 flex justify-center">
          <Image src="/scheduled_logo.svg" alt="Scheduled" width={140} height={32} />
        </div>

        <h1 className="mb-2 text-center text-xl font-semibold text-gray-900">
          Permissions Required
        </h1>

        <p className="mb-6 text-center text-sm text-gray-600">
          Scheduled needs access to your Gmail and Google Calendar to work.
          Please make sure to check <strong>Select all</strong> on the permissions screen.
        </p>

        <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <p className="mb-3 text-sm font-medium text-amber-800">
            On the next screen, click &quot;Select all&quot; to grant the required permissions:
          </p>
          <ul className="space-y-2 text-sm text-amber-700">
            <li className="flex items-start gap-2">
              <span className="mt-0.5 text-amber-500">&#10003;</span>
              <span><strong>View email messages</strong> &mdash; so we can detect scheduling requests</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-0.5 text-amber-500">&#10003;</span>
              <span><strong>Manage drafts</strong> &mdash; so we can create draft replies for you</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-0.5 text-amber-500">&#10003;</span>
              <span><strong>Google Calendar</strong> &mdash; so we can check your availability</span>
            </li>
          </ul>
        </div>

        <div className="mb-6 flex justify-center">
          <div className="rounded-lg border-2 border-amber-300 p-1">
            <img
              src="/google-permissions-guide.png"
              alt="Click Select all on the Google permissions screen"
              className="rounded"
              width={400}
            />
          </div>
        </div>

        {retryUrl ? (
          <a
            href={retryUrl}
            className="block w-full rounded-lg bg-blue-600 px-4 py-3 text-center text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            Try Again
          </a>
        ) : (
          <p className="text-center text-sm text-gray-500">
            Please go back and try connecting your Google account again.
          </p>
        )}

        <p className="mt-4 text-center text-xs text-gray-400">
          We never read your email content beyond checking if a message is about scheduling.
          Your data stays private.
        </p>
      </div>
    </div>
  );
}

export default function PermissionsRequiredPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <p className="text-gray-500">Loading...</p>
      </div>
    }>
      <PermissionsContent />
    </Suspense>
  );
}
