import { api } from './api';

const BASE_URL = process.env.NEXT_PUBLIC_CONTROL_PLANE_URL || '';

export function track(event: string, properties?: Record<string, unknown>) {
  api('/web/api/v1/events/track', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ event, properties: properties || {} }),
  }).catch(() => {}); // fire-and-forget
}

export function trackPageEvent(event: string, properties?: Record<string, unknown>) {
  fetch(`${BASE_URL}/web/api/v1/events/page`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ event, properties: properties || {} }),
  }).catch(() => {}); // fire-and-forget, no auth required
}
