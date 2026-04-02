'use client';

import { useState } from 'react';
import { ArrowLeft, Check } from 'lucide-react';

const CALENDAR_GOALS = [
  'Trying to protect my calendar',
  'Trying to schedule time with other people',
];

const SCHEDULING_WITH = [
  { label: 'Above you in status', value: 'above' },
  { label: 'Peers', value: 'peer' },
  { label: 'Below you in status', value: 'below' },
  { label: 'Mix of all', value: 'mix' },
];

const PAST_TOOLS = [
  'Calendly',
  'Howie',
  'Fxyer',
  'Cal.com',
  'Blockit',
  'Scheduling AI by Superhuman',
  'Scheduling AI by Gmail',
];

export interface SchedulingContextData {
  calendarGoal: string;
  schedulingWith: string;
  pastTools: string[];
  pastToolsOther: string;
}

interface SchedulingContextStepProps {
  initialValue: SchedulingContextData;
  onContinue: (data: SchedulingContextData) => void;
  onBack: () => void;
}

export default function SchedulingContextStep({ initialValue, onContinue, onBack }: SchedulingContextStepProps) {
  const [calendarGoal, setCalendarGoal] = useState(initialValue.calendarGoal);
  const [schedulingWith, setSchedulingWith] = useState(initialValue.schedulingWith);
  const [pastTools, setPastTools] = useState<string[]>(initialValue.pastTools);
  const [pastToolsOther, setPastToolsOther] = useState(initialValue.pastToolsOther);

  function toggleTool(tool: string) {
    setPastTools((prev) =>
      prev.includes(tool) ? prev.filter((t) => t !== tool) : [...prev, tool]
    );
  }

  return (
    <div>
      <button
        onClick={onBack}
        className="mb-4 flex cursor-pointer items-center gap-1 text-sm text-gray-400 transition-colors hover:text-gray-600"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back
      </button>

      <h1 className="text-xl font-semibold text-gray-900">
        Tell us about your scheduling
      </h1>

      {/* Calendar goal */}
      <div className="mt-6">
        <p className="text-sm font-medium text-gray-700">Calendar work is mainly:</p>
        <div className="mt-2 space-y-2">
          {CALENDAR_GOALS.map((goal) => (
            <button
              key={goal}
              onClick={() => setCalendarGoal(goal)}
              className={`flex w-full cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 text-left text-sm transition-colors ${
                calendarGoal === goal
                  ? 'border-[#43614a] bg-[#43614a]/5 text-gray-900'
                  : 'border-gray-200 text-gray-600 hover:border-gray-300'
              }`}
            >
              <div className={`flex h-4.5 w-4.5 flex-shrink-0 items-center justify-center rounded-full border ${
                calendarGoal === goal ? 'border-[#43614a] bg-[#43614a]' : 'border-gray-300'
              }`}>
                {calendarGoal === goal && <Check className="h-3 w-3 text-white" />}
              </div>
              {goal}
            </button>
          ))}
        </div>
      </div>

      {/* Who you schedule with */}
      <div className="mt-6">
        <p className="text-sm font-medium text-gray-700">Most of the scheduling you do is with people:</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {SCHEDULING_WITH.map(({ label, value }) => (
            <button
              key={value}
              onClick={() => setSchedulingWith(value)}
              className={`cursor-pointer rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
                schedulingWith === value
                  ? 'border-[#43614a] bg-[#43614a]/10 text-[#43614a]'
                  : 'border-gray-200 text-gray-600 hover:border-gray-300'
              }`}
            >
              {schedulingWith === value && <Check className="mr-1 -ml-0.5 inline h-3.5 w-3.5" />}
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Past tools */}
      <div className="mt-6">
        <p className="text-sm font-medium text-gray-700">Have you tried any of these before?</p>
        <p className="mt-0.5 text-xs text-gray-400">Select all that apply</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {PAST_TOOLS.map((tool) => (
            <button
              key={tool}
              onClick={() => toggleTool(tool)}
              className={`cursor-pointer rounded-full border px-3.5 py-1.5 text-sm transition-colors ${
                pastTools.includes(tool)
                  ? 'border-[#43614a] bg-[#43614a]/10 text-[#43614a] font-medium'
                  : 'border-gray-200 text-gray-600 hover:border-gray-300'
              }`}
            >
              {pastTools.includes(tool) && <Check className="mr-1 -ml-0.5 inline h-3.5 w-3.5" />}
              {tool}
            </button>
          ))}
          <button
            onClick={() => toggleTool('__other__')}
            className={`cursor-pointer rounded-full border px-3.5 py-1.5 text-sm transition-colors ${
              pastTools.includes('__other__')
                ? 'border-[#43614a] bg-[#43614a]/10 text-[#43614a] font-medium'
                : 'border-gray-200 text-gray-600 hover:border-gray-300'
            }`}
          >
            {pastTools.includes('__other__') && <Check className="mr-1 -ml-0.5 inline h-3.5 w-3.5" />}
            Other
          </button>
        </div>
        {pastTools.includes('__other__') && (
          <input
            type="text"
            value={pastToolsOther}
            onChange={(e) => setPastToolsOther(e.target.value)}
            placeholder="What else have you tried?"
            className="mt-2 w-full rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-900 placeholder-gray-400 outline-none focus:border-[#43614a] focus:ring-1 focus:ring-[#43614a]"
          />
        )}
      </div>

      <button
        onClick={() => onContinue({ calendarGoal, schedulingWith, pastTools, pastToolsOther })}
        className="mt-8 inline-flex w-full cursor-pointer items-center justify-center rounded-xl bg-[#43614a] px-6 py-4 text-base font-semibold text-white transition-colors hover:bg-[#527559]"
      >
        Continue
      </button>
    </div>
  );
}
