import { User, ExamRoom, Invigilator, RoomMonitoringSummary, ViolationEvent } from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

let refreshHandler: (() => Promise<string | null>) | null = null;

export function registerAuthRefresh(handler: () => Promise<string | null>) {
  refreshHandler = handler;
}

export async function apiRequest(endpoint: string, options: RequestInit = {}) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('smartexam_token') : null;
  const headers = new Headers(options.headers || {});

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  let response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (response.status === 401 && refreshHandler) {
    const newToken = await refreshHandler();
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
  const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  if (!token) return `${base}/api/monitoring/video-feed`;
  return `${base}/api/monitoring/video-feed?token=${encodeURIComponent(token)}`;
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
