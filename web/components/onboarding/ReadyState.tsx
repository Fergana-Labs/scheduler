'use client';

import { useState } from 'react';
import SystemToggle from './SystemToggle';
import AutopilotToggle from './AutopilotToggle';
import SalesEmailToggle from './SalesEmailToggle';
import GuideEditor from './GuideEditor';
import CalendarLink from './CalendarLink';
import BrandingToggle from './BrandingToggle';
import ReasoningEmailToggle from './ReasoningEmailToggle';
import CalendarPicker from './CalendarPicker';
import DraftAutoDeleteToggle from './DraftAutoDeleteToggle';
import DisconnectButton from './DisconnectButton';
import BillingSettings from './BillingSettings';
import ModeSwitcher from './ModeSwitcher';

interface Guide {
  name: string;
  content: string;
  updated_at: string;
  is_default?: boolean;
}

interface ReadyStateProps {
  systemEnabled: boolean;
  autopilotEnabled: boolean;
  processSalesEmails: boolean;
  brandingEnabled: boolean;
  reasoningEmailsEnabled: boolean;
  draftAutoDeleteEnabled: boolean;
  calendarId: string | null;
  guides: Guide[];
  schedulingMode: string;
  onDisconnected: () => void;
}

export default function ReadyState({
  systemEnabled,
  autopilotEnabled,
  processSalesEmails,
  brandingEnabled,
  reasoningEmailsEnabled,
  draftAutoDeleteEnabled,
  calendarId,
  guides,
  schedulingMode,
  onDisconnected,
}: ReadyStateProps) {
  const [mode, setMode] = useState(schedulingMode);
  const schedulingGuide = guides.find((g) => g.name === 'scheduling_preferences');
  const emailGuide = guides.find((g) => g.name === 'email_style');
  const isDraft = mode === 'draft';

  return (
    <div className="space-y-3">
      <ModeSwitcher initialMode={schedulingMode} initialGuides={guides} onModeChange={setMode} />

      {/* Draft-mode only settings */}
      {isDraft && (
        <>
          <ReasoningEmailToggle initialEnabled={reasoningEmailsEnabled} />
          <AutopilotToggle initialEnabled={autopilotEnabled} />
          <SalesEmailToggle initialEnabled={processSalesEmails} />
          <DraftAutoDeleteToggle initialEnabled={draftAutoDeleteEnabled} />
        </>
      )}

      {schedulingGuide && (
        <GuideEditor
          name="scheduling_preferences"
          label="Scheduling Preferences"
          initialContent={schedulingGuide.content}
          updatedAt={schedulingGuide.updated_at}
          isDefault={schedulingGuide.is_default}
        />
      )}

      {/* Email style guide only in draft mode */}
      {isDraft && emailGuide && (
        <GuideEditor
          name="email_style"
          label="Email Style"
          initialContent={emailGuide.content}
          updatedAt={emailGuide.updated_at}
          isDefault={emailGuide.is_default}
        />
      )}

      <CalendarPicker />

      {calendarId && <CalendarLink calendarId={calendarId} />}

      {isDraft && <BrandingToggle initialEnabled={brandingEnabled} />}

      <BillingSettings />

      <div className="pt-4">
        <DisconnectButton onDisconnected={onDisconnected} />
      </div>
    </div>
  );
}
