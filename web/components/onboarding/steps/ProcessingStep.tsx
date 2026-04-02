'use client';

import PendingState from '../PendingState';
import FailedState from '../FailedState';

interface ProcessingStepProps {
  agents: Record<string, string> | null;
  failed: boolean;
  failedError: string | null;
  onRetry: () => void;
  email: string;
  mode: 'bot' | 'draft';
}

export default function ProcessingStep({
  agents,
  failed,
  failedError,
  onRetry,
  email,
  mode,
}: ProcessingStepProps) {
  return (
    <div>
      <h1 className="text-xl font-semibold text-gray-900">
        {failed ? 'Something went wrong' : 'Setting things up'}
      </h1>
      <p className="mt-1 text-sm text-gray-500">
        {failed
          ? 'We ran into an issue. You can try again.'
          : mode === 'bot'
            ? `Learning your calendar preferences...`
            : `Analyzing your email and calendar to learn your style...`
        }
      </p>
      <p className="mt-1 text-xs text-gray-400">
        Signed in as {email}
      </p>

      <div className="mt-6">
        {failed ? (
          <FailedState error={failedError} onRetry={onRetry} />
        ) : (
          <PendingState agents={agents} mode={mode} />
        )}
      </div>
    </div>
  );
}
