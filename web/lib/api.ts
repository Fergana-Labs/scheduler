const BASE_URL = process.env.NEXT_PUBLIC_CONTROL_PLANE_URL;

const SESSION_KEY = 'stash_session';

export function captureSessionFromURL() {
  if (typeof window === 'undefined') return;
  const params = new URLSearchParams(window.location.search);
  // Support both 'token' (hosted auth providers) and 'session' (legacy) params.
  const token = params.get('token') || params.get('session');
  if (token) {
    localStorage.setItem(SESSION_KEY, token);
    // Remove token and transient params from URL without reload
    params.delete('token');
    params.delete('session');
    params.delete('checkout');
    const clean = params.toString();
    const newUrl = window.location.pathname + (clean ? `?${clean}` : '');
    window.history.replaceState({}, '', newUrl);
  }
}

export function getSession(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(SESSION_KEY);
}

export function clearSession() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(SESSION_KEY);
}

export async function api<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getSession();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const { headers: _dropHeaders, ...restOptions } = options;
  const res = await fetch(`${BASE_URL}${path}`, {
    credentials: 'include',
    ...restOptions,
    headers,
  });

  if (!res.ok) {
    // Parse 403 subscription_required so callers can handle it
    if (res.status === 403) {
      const body = await res.json().catch(() => ({}));
      if (body.detail === 'subscription_required') {
        throw new Error('subscription_required');
      }
    }
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}
