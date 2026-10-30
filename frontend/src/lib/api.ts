import { User, ExamRoom, Invigilator, RoomMonitoringSummary, ViolationEvent } from './types';
function getRuntimeApiBase(): string {
  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:';
    return `${protocol}//${window.location.hostname}:8000`;
  }
  return process.env.NEXT_PUBLIC_API_URL || 'http://192.168.1.9:8000';
}

const API_BASE = getRuntimeApiBase();

let refreshHandler: (() => Promise<string | null>) | null = null;
let refreshInFlight: Promise<string | null> | null = null;

export function registerAuthRefresh(handler: () => Promise<string | null>) {
  refreshHandler = handler;
}

export function isTokenExpired(token?: string | null, bufferSeconds = 10): boolean {
  if (!token) return true;
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return true;
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=');
    const payload = JSON.parse(atob(padded));
    if (typeof payload.exp !== 'number') return true;
    return payload.exp * 1000 <= Date.now() + bufferSeconds * 1000;
  } catch {
    return true;
  }
}

export function getTokenRemainingMs(token?: string | null): number {
  if (!token) return 0;
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return 0;
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=');
    const payload = JSON.parse(atob(padded));
    if (typeof payload.exp !== 'number') return 0;
    return Math.max(0, payload.exp * 1000 - Date.now());
  } catch {
    return 0;
  }
}

export async function triggerTokenRefresh(): Promise<string | null> {
  if (!refreshHandler) return null;
  if (!refreshInFlight) {
    refreshInFlight = refreshHandler().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

export async function apiRequest(endpoint: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers || {});

  if (!headers.has('Authorization') && typeof window !== 'undefined') {
    let token = localStorage.getItem('smartexam_token');
    if (token && isTokenExpired(token)) {
      token = await triggerTokenRefresh();
    }
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
  }

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  let response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (response.status === 401 && refreshHandler) {
    const newToken = await triggerTokenRefresh();
    if (newToken) {
      headers.set('Authorization', `Bearer ${newToken}`);
      response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers,
      });
    }
  }

  return response;
}

// Auth endpoints
export async function login(username: string, password: string) {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to login');
  }
  return res.json();
}

export async function refreshToken(refreshTokenStr: string) {
  const res = await fetch(`${API_BASE}/api/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshTokenStr }),
  });
  if (!res.ok) {
    throw new Error('Refresh token expired or invalid');
  }
  return res.json();
}

export async function getCurrentUser(token?: string): Promise<User> {
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await apiRequest('/api/auth/me', { headers });
  if (!res.ok) throw new Error('Failed to load user profile');
  return res.json();
}

// Admin endpoints (REST only - No WebSockets)
export async function getAdminRooms(): Promise<ExamRoom[]> {
  const res = await apiRequest('/api/admin/rooms');
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to load exam rooms');
  }
  return res.json();
}

export async function createAdminRoom(data: { name: string; building?: string; capacity?: number }): Promise<ExamRoom> {
  const res = await apiRequest('/api/admin/rooms', {
    method: 'POST',
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to create exam room');
  }
  return res.json();
}

export async function getAdminInvigilators(): Promise<Invigilator[]> {
  const res = await apiRequest('/api/admin/invigilators');
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to load invigilators');
  }
  return res.json();
}

export async function createAdminInvigilator(data: {
  username: string;
  password: string;
  email?: string;
  assigned_room_id: number;
}): Promise<Invigilator> {
  const res = await apiRequest('/api/admin/invigilators', {
    method: 'POST',
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to create invigilator');
  }
  return res.json();
}

export async function updateAdminInvigilator(
  id: number,
  data: { is_active?: boolean; assigned_room_id?: number; password?: string }
): Promise<Invigilator> {
  const res = await apiRequest(`/api/admin/invigilators/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to update invigilator');
  }
  return res.json();
}

export async function deleteAdminInvigilator(id: number): Promise<void> {
  const res = await apiRequest(`/api/admin/invigilators/${id}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to delete invigilator');
  }
}

// Monitoring endpoints (Strictly room-scoped for assigned invigilator)
export async function getMyRoom(): Promise<ExamRoom> {
  const res = await apiRequest('/api/monitoring/my-room');
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to load assigned room');
  }
  return res.json();
}

export async function getMyRoomSummary(): Promise<RoomMonitoringSummary> {
  const res = await apiRequest('/api/monitoring/summary');
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to load room monitoring summary');
  }
  return res.json();
}

export async function getMyRoomEvents(limit = 50): Promise<ViolationEvent[]> {
  const res = await apiRequest(`/api/monitoring/events?limit=${limit}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to load room events');
  }
  return res.json();
}

export function getVideoFeedUrl(token?: string | null): string {
  const base = getRuntimeApiBase();

  if (!token) return `${base}/api/monitoring/video-feed`;

  return `${base}/api/monitoring/video-feed?token=${encodeURIComponent(token)}`;
}

export function getEvidenceUrl(evidenceUrl?: string | null): string {
  if (!evidenceUrl) return '';
  const trimmed = evidenceUrl.trim();
  if (!trimmed) return '';
  if (/^(https?:|data:|blob:)/i.test(trimmed)) {
    return trimmed;
  }
  const base = getRuntimeApiBase().replace(/\/$/, '');
  if (trimmed.startsWith('/')) {
    return `${base}${trimmed}`;
  }
  if (trimmed.startsWith('api/') || trimmed.startsWith('evidence/')) {
    return `${base}/${trimmed}`;
  }
  return `${base}/api/events/evidence/${encodeURIComponent(trimmed)}`;
}

export function getMonitoringWsUrl(token?: string | null): string {
  if (!token || isTokenExpired(token, 0)) return '';
  if (typeof window !== 'undefined') {
    const wsBase = API_BASE.replace(/^http/, 'ws').replace(/\/$/, '');
    return `${wsBase}/ws/monitoring?token=${encodeURIComponent(token)}`;
  }
  const configuredWs = process.env.NEXT_PUBLIC_WS_URL;
  if (configuredWs) {
    const baseWs = configuredWs.replace(/\/ws\/(dashboard|monitoring)\/?$/, '').replace(/\/$/, '');
    return `${baseWs}/ws/monitoring?token=${encodeURIComponent(token)}`;
  }
  const apiBase = process.env.NEXT_PUBLIC_API_URL;
  if (apiBase) {
    const wsBase = apiBase.replace(/^http/, 'ws').replace(/\/$/, '');
    return `${wsBase}/ws/monitoring?token=${encodeURIComponent(token)}`;
  }
  return '';
}

export async function pauseExam(reason = 'Proctor paused exam') {
  const res = await apiRequest(`/api/exams/pause?reason=${encodeURIComponent(reason)}`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to pause exam');
  return res.json();
}

export async function resumeExam() {
  const res = await apiRequest('/api/exams/resume', { method: 'POST' });
  if (!res.ok) throw new Error('Failed to resume exam');
  return res.json();
}
