declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
  }
}

import { api } from './api';

const BASE_URL = process.env.NEXT_PUBLIC_CONTROL_PLANE_URL || '';

function getSessionId(): string {
  const key = 'scheduled_session_id';
  let id = sessionStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(key, id);
  }
  return id;
}

export function setGAUserId(userId: string) {
  if (typeof window !== 'undefined' && typeof window.gtag === 'function') {
    window.gtag('set', { user_id: userId });
  }
}

export function track(event: string, properties?: Record<string, unknown>) {
  api('/web/api/v1/events/track', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ event, properties: properties || {} }),
  }).catch(() => {}); // fire-and-forget
}

export function trackPageEvent(event: string, properties?: Record<string, unknown>) {
  const merged = { ...properties, session_id: getSessionId() };
  fetch(`${BASE_URL}/web/api/v1/events/page`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ event, properties: merged }),
  }).catch(() => {}); // fire-and-forget, no auth required
}
