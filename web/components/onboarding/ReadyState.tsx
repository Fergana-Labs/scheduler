'use client';

import SystemToggle from './SystemToggle';
import AutopilotToggle from './AutopilotToggle';
import GuideEditor from './GuideEditor';
import CalendarLink from './CalendarLink';
import BrandingToggle from './BrandingToggle';
import DisconnectButton from './DisconnectButton';

interface Guide {
  name: string;
  content: string;
  updated_at: string;
}

interface ReadyStateProps {
  systemEnabled: boolean;
  autopilotEnabled: boolean;
  brandingEnabled: boolean;
  calendarId: string | null;
  guides: Guide[];
}

export default function ReadyState({
  systemEnabled,
  autopilotEnabled,
  brandingEnabled,
  calendarId,
  guides,
}: ReadyStateProps) {
  const schedulingGuide = guides.find((g) => g.name === 'scheduling_preferences');
  const emailGuide = guides.find((g) => g.name === 'email_style');

  return (
    <div className="space-y-3">
      <SystemToggle initialEnabled={systemEnabled} />
      <AutopilotToggle initialEnabled={autopilotEnabled} />

      {schedulingGuide && (
        <GuideEditor
          name="scheduling_preferences"
          label="Scheduling Preferences"
          initialContent={schedulingGuide.content}
          updatedAt={schedulingGuide.updated_at}
        />
      )}

      {emailGuide && (
        <GuideEditor
          name="email_style"
          label="Email Style"
          initialContent={emailGuide.content}
          updatedAt={emailGuide.updated_at}
        />
      )}

      {calendarId && <CalendarLink calendarId={calendarId} />}

      <BrandingToggle initialEnabled={brandingEnabled} />

      <div className="pt-4">
        <DisconnectButton />
      </div>
    </div>
  );
}
