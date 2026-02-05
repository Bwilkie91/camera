const API_BASE = import.meta.env.VITE_API_URL || '';

const fetchOpts: RequestInit = { credentials: 'include' };

function handle401(r: Response) {
  if (r.status === 401) {
    r.clone().json().catch(() => ({})).then((d: { error?: string }) => {
      if (d?.error === 'session_timeout') window.location.assign('/login?timeout=1');
    });
  }
  return r;
}
function get(url: string) {
  return fetch(url, { ...fetchOpts, method: 'GET' }).then(handle401);
}
function post(url: string, body?: object) {
  return fetch(url, { ...fetchOpts, method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined }).then(handle401);
}
function put(url: string, body?: object) {
  return fetch(url, { ...fetchOpts, method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined }).then(handle401);
}

export type Stream = {
  id: string;
  name: string;
  type: string;
  url: string;
  camera_id: string;
};

export type AIDataRow = {
  date: string;
  time: string;
  individual?: string;
  facial_features?: string;
  object: string;
  pose: string;
  emotion: string;
  scene: string;
  license_plate?: string;
  event: string;
  crowd_count: number;
  audio_event?: string;
  device_mac?: string;
  thermal_signature?: string;
  camera_id?: string;
};

export type EventRow = {
  id: number;
  event_type: string;
  camera_id: string | null;
  site_id?: string | null;
  timestamp: string;
  timestamp_utc?: string | null;
  metadata: string | null;
  severity: string;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  integrity_hash?: string | null;
};

export type Site = { id: string; name: string; map_url: string | null; timezone: string | null };
export type CameraPosition = { camera_id: string; site_id: string; x: number; y: number; label: string | null };

export async function fetchSites(): Promise<Site[]> {
  const r = await get(`${API_BASE}/sites`);
  if (!r.ok) throw new Error('Failed to fetch sites');
  return r.json();
}

export async function fetchCameraPositions(siteId?: string): Promise<CameraPosition[]> {
  const sp = siteId ? `?site_id=${encodeURIComponent(siteId)}` : '';
  const r = await get(`${API_BASE}/camera_positions${sp}`);
  if (!r.ok) throw new Error('Failed to fetch camera positions');
  return r.json();
}

export async function fetchStreams(): Promise<Stream[]> {
  const r = await get(`${API_BASE}/streams`);
  if (!r.ok) throw new Error('Failed to fetch streams');
  return r.json();
}

export async function fetchGetData(params?: { limit?: number; offset?: number; date_from?: string; date_to?: string }): Promise<AIDataRow[]> {
  const sp = new URLSearchParams();
  if (params?.limit != null) sp.set('limit', String(params.limit));
  if (params?.offset != null) sp.set('offset', String(params.offset));
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  const r = await get(`${API_BASE}/get_data?${sp}`);
  if (!r.ok) throw new Error('Failed to fetch AI data');
  return r.json();
}

export async function fetchEvents(params?: {
  limit?: number;
  offset?: number;
  acknowledged?: string;
  date_from?: string;
  date_to?: string;
  severity?: string;
  event_type?: string;
}): Promise<EventRow[]> {
  const sp = new URLSearchParams();
  if (params?.limit != null) sp.set('limit', String(params.limit));
  if (params?.offset != null) sp.set('offset', String(params.offset));
  if (params?.acknowledged) sp.set('acknowledged', params.acknowledged);
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  if (params?.severity) sp.set('severity', params.severity);
  if (params?.event_type) sp.set('event_type', params.event_type);
  const r = await get(`${API_BASE}/events?${sp}`);
  if (!r.ok) throw new Error('Failed to fetch events');
  return r.json();
}

export async function acknowledgeEvent(eventId: number, user?: string): Promise<void> {
  const r = await post(`${API_BASE}/events/${eventId}/acknowledge`, { user: user || 'operator' });
  if (!r.ok) throw new Error('Failed to acknowledge');
}

export async function fetchRecordingStatus(): Promise<{ recording: boolean }> {
  const r = await get(`${API_BASE}/recording`);
  if (!r.ok) throw new Error('Failed to fetch recording status');
  return r.json();
}

/** Data collection config: event_types, capture_audio, ai_detail (full | minimal). Only applies while recording. */
export type RecordingConfig = {
  event_types: string[];
  capture_audio: boolean;
  capture_thermal: boolean;
  capture_wifi: boolean;
  ai_detail: 'full' | 'minimal';
};
export async function fetchRecordingConfig(): Promise<RecordingConfig> {
  const r = await get(`${API_BASE}/recording_config`);
  if (!r.ok) throw new Error('Failed to fetch recording config');
  return r.json();
}
export async function updateRecordingConfig(updates: Partial<RecordingConfig>): Promise<RecordingConfig> {
  const r = await post(`${API_BASE}/recording_config`, updates);
  if (!r.ok) throw new Error('Failed to update recording config');
  return r.json();
}

export async function fetchHealth(): Promise<{ status: string; recording?: boolean; uptime_seconds?: number }> {
  const r = await get(`${API_BASE}/health`);
  if (!r.ok) throw new Error('Health check failed');
  return r.json();
}

export type CameraStatusItem = { id: string; name: string; status: 'ok' | 'no_signal' | 'offline'; resolution: string | null; source: string | null; last_frame_utc?: string | null; last_offline_utc?: string | null; flapping?: boolean };
export type SystemStatus = {
  status: 'ok' | 'degraded';
  db_ok: boolean;
  recording: boolean;
  uptime_seconds: number;
  cameras: CameraStatusItem[];
  storage_used_bytes?: number;
  storage_free_bytes?: number;
  storage_total_bytes?: number;
  recording_count?: number;
  retention_days?: number;
  audio_enabled?: boolean;
  feature_flags?: { audio_capture: boolean; lpr: boolean; emotion: boolean; wifi_sniff: boolean; reid: boolean };
  privacy_preset?: 'minimal' | 'full';
  home_away_mode?: 'home' | 'away';
};
export async function fetchSystemStatus(): Promise<SystemStatus> {
  const r = await get(`${API_BASE}/api/v1/system_status`);
  if (!r.ok) throw new Error('System status failed');
  return r.json();
}

/** Transparency: what is recorded/analyzed (civilian ethics). */
export type WhatWeCollect = {
  video: boolean;
  audio: boolean;
  motion: boolean;
  loitering: boolean;
  line_crossing: boolean;
  lpr: boolean;
  emotion_or_face: boolean;
  wifi_presence: boolean;
  thermal: boolean;
  retention_days: number;
  privacy_preset: string;
};
export async function fetchWhatWeCollect(): Promise<WhatWeCollect> {
  const r = await get(`${API_BASE}/api/v1/what_we_collect`);
  if (!r.ok) throw new Error('Failed to fetch what we collect');
  return r.json();
}

export type DetectedCamera = { index: number | string; path: string; opened: boolean; resolution: string | null; name?: string };
export async function fetchCamerasDetect(): Promise<{ detected: DetectedCamera[] }> {
  const r = await get(`${API_BASE}/api/v1/cameras/detect`);
  if (!r.ok) throw new Error('Camera detection failed');
  return r.json();
}

export type DetectedMicrophone = { index: number; name: string; sample_rate: number; channels: number };
export async function fetchAudioDetect(): Promise<{ detected: DetectedMicrophone[]; audio_enabled: boolean }> {
  const r = await get(`${API_BASE}/api/v1/audio/detect`);
  if (!r.ok) throw new Error('Audio detection failed');
  return r.json();
}

export type DevicesResponse = {
  cameras: DetectedCamera[];
  microphones: DetectedMicrophone[];
  audio_enabled: boolean;
  camera_sources_auto: boolean;
};
export async function fetchDevices(): Promise<DevicesResponse> {
  const r = await get(`${API_BASE}/api/v1/devices`);
  if (!r.ok) throw new Error('Devices list failed');
  return r.json();
}

export async function toggleRecording(): Promise<{ recording: boolean }> {
  const r = await post(`${API_BASE}/toggle_recording`);
  if (!r.ok) throw new Error('Failed to toggle recording');
  return r.json();
}

export async function moveCamera(direction: 'left' | 'right' | 'stop'): Promise<{ status: string }> {
  const r = await post(`${API_BASE}/move_camera`, { direction });
  if (!r.ok) throw new Error(r.status === 503 ? 'PTZ not available' : 'Failed to move camera');
  return r.json();
}

/** Toggle motion detection on/off. Backend returns new state. */
export async function toggleMotion(enabled: boolean): Promise<{ motion: boolean }> {
  const r = await post(`${API_BASE}/toggle_motion`, { motion: enabled });
  if (!r.ok) throw new Error('Failed to toggle motion');
  return r.json();
}

export type Me = { authenticated: boolean; username?: string; role?: string; password_expires_in_days?: number };
export async function fetchMe(): Promise<Me> {
  const r = await get(`${API_BASE}/me`);
  if (r.status === 401) return { authenticated: false };
  if (!r.ok) throw new Error('Failed to fetch session');
  return r.json();
}
/** When server has AUTO_LOGIN=1, creates session as admin so user can skip login page. */
export async function autoLogin(): Promise<{ success: boolean }> {
  const r = await get(`${API_BASE}/api/v1/auto_login`);
  if (r.status === 404) return { success: false };
  const data = await r.json().catch(() => ({}));
  return { success: !!data?.success };
}
export async function changePassword(currentPassword: string, newPassword: string): Promise<{ success: boolean; error?: string }> {
  const r = await post(`${API_BASE}/change_password`, { current_password: currentPassword, new_password: newPassword });
  const data = await r.json();
  if (!r.ok) return { success: false, error: data?.error || 'Failed to change password' };
  return data;
}
export type LoginResult = {
  success: boolean;
  role?: string;
  locked?: boolean;
  locked_until_utc?: string | null;
  require_mfa?: boolean;
  mfa_token?: string;
  password_expired?: boolean;
  password_expires_in_days?: number;
};
export async function login(username: string, password: string): Promise<LoginResult> {
  const r = await post(`${API_BASE}/login`, { username, password });
  const data = await r.json().catch(() => ({})) as LoginResult;
  if (r.status === 423) return { ...data, success: false };
  if (r.status === 403) return { ...data, success: false };
  return data;
}
export async function verifyTotp(mfaToken: string, code: string): Promise<{ success: boolean; role?: string }> {
  const r = await post(`${API_BASE}/login/verify_totp`, { mfa_token: mfaToken, code });
  return r.json().catch(() => ({ success: false }));
}
export async function logout(): Promise<void> {
  await post(`${API_BASE}/logout`);
}

export type MfaStatus = { enabled: boolean; available: boolean };
export async function fetchMfaStatus(): Promise<MfaStatus> {
  const r = await get(`${API_BASE}/mfa/status`);
  if (r.status === 401) return { enabled: false, available: false };
  if (!r.ok) throw new Error('Failed to fetch MFA status');
  return r.json();
}
export async function mfaSetup(): Promise<{ secret: string; provisioning_uri: string }> {
  const r = await post(`${API_BASE}/mfa/setup`);
  if (!r.ok) throw new Error('MFA setup failed');
  return r.json();
}
export async function mfaConfirm(code: string): Promise<{ success: boolean }> {
  const r = await post(`${API_BASE}/mfa/confirm`, { code });
  return r.json();
}

export type AuditEntry = { id: number; user_id: string; action: string; resource: string | null; timestamp: string; details: string | null };
/** mine: true = only current user's entries (My access history). */
export async function fetchAuditLog(limit?: number, mine?: boolean): Promise<AuditEntry[]> {
  const sp = new URLSearchParams();
  if (limit != null) sp.set('limit', String(limit));
  if (mine) sp.set('mine', '1');
  const url = `${API_BASE}/audit_log${sp.toString() ? `?${sp}` : ''}`;
  const r = await get(url);
  if (r.status === 403) throw new Error('Forbidden');
  if (!r.ok) throw new Error('Failed to fetch audit log');
  return r.json();
}

/** Download audit log as CSV with SHA-256 (admin). */
export async function downloadAuditLogExport(): Promise<Blob> {
  const r = await get(`${API_BASE}/audit_log/export`);
  if (r.status === 403) throw new Error('Forbidden');
  if (!r.ok) throw new Error('Failed to export audit log');
  return r.blob();
}

/** Verify audit log integrity (NIST AU-9). Admin only. */
export type AuditLogVerifyResult = { verified: number; mismatched: number; total: number; message?: string };
export async function fetchAuditLogVerify(): Promise<AuditLogVerifyResult> {
  const r = await get(`${API_BASE}/audit_log/verify`);
  if (r.status === 403) throw new Error('Forbidden');
  if (!r.ok) throw new Error('Failed to verify audit log');
  return r.json();
}

/** dateFrom/dateTo: optional YYYY-MM-DD for incident bundle range. */
export async function downloadExportData(dateFrom?: string, dateTo?: string): Promise<Blob> {
  const sp = new URLSearchParams();
  if (dateFrom) sp.set('date_from', dateFrom);
  if (dateTo) sp.set('date_to', dateTo);
  const url = `${API_BASE}/export_data${sp.toString() ? `?${sp}` : ''}`;
  const r = await get(url);
  if (r.status === 403) throw new Error('Forbidden: operator or admin role required');
  if (!r.ok) throw new Error('Export failed');
  return r.blob();
}

export type AnalyticsConfig = {
  loiter_zones: number[][][];
  loiter_seconds: number;
  crossing_lines: number[][];
  privacy_preset?: 'minimal' | 'full';
  home_away_mode?: 'home' | 'away';
  recording_signage_reminder?: string;
  privacy_policy_url?: string;
};
export async function fetchConfig(): Promise<AnalyticsConfig> {
  const r = await get(`${API_BASE}/config`);
  if (!r.ok) throw new Error('Failed to fetch config');
  return r.json();
}
export async function updateConfig(updates: Partial<AnalyticsConfig>): Promise<{ success: boolean; error?: string }> {
  const r = await fetch(`${API_BASE}/config`, {
    ...fetchOpts,
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  }).then(handle401);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) return { success: false, error: data?.error || 'Failed to update config' };
  return data;
}

/** Reset server data: delete all events and ai_data so dashboard counts go to zero. Admin only. Recordings and users are not affected. */
export async function resetServerData(): Promise<{ success: boolean; error?: string }> {
  const r = await post(`${API_BASE}/api/v1/reset_data`);
  const data = await r.json().catch(() => ({}));
  if (r.status === 403) return { success: false, error: 'Admin role required' };
  if (r.status === 404) return { success: false, error: 'Reset endpoint not found. Restart the Flask server to load the latest code.' };
  if (!r.ok) return { success: false, error: (data && typeof data.error === 'string' ? data.error : null) || `Reset failed (${r.status})` };
  return data as { success: boolean };
}

export type RecordingEntry = { name: string; size_bytes: number; created_utc: string };
export type RecordingsResponse = { recordings: RecordingEntry[]; forbidden?: boolean };
export async function fetchRecordings(): Promise<RecordingsResponse> {
  const r = await get(`${API_BASE}/recordings`);
  if (r.status === 403) return { recordings: [], forbidden: true };
  if (!r.ok) throw new Error('Failed to fetch recordings');
  return r.json();
}

/** URL for inline playback (use in <video src={...} /> with credentials). Use format=mp4 for browser-friendly playback when backend has ffmpeg. */
export function getRecordingPlayUrl(name: string, preferMp4 = true): string {
  const base = `${API_BASE}/recordings/${encodeURIComponent(name)}/play`;
  return preferMp4 ? `${base}?format=mp4` : base;
}

/** Fetch recording for playback with credentials; returns blob so caller can create a blob URL and revoke it when done. */
export async function fetchRecordingPlayBlob(name: string, preferMp4 = true): Promise<Blob> {
  const url = getRecordingPlayUrl(name, preferMp4);
  const r = await get(url);
  if (r.status === 403) throw new Error('Sign in required to play recordings.');
  if (r.status === 404) throw new Error('Recording not found.');
  if (!r.ok) throw new Error('Playback failed.');
  return r.blob();
}

/**
 * Find a recording that likely contains the given event timestamp, and the offset in seconds into that recording.
 * Recordings are named recording_<unixStart>.avi; we pick the one where start <= eventTime.
 */
export function findRecordingAtMoment(
  recordings: RecordingEntry[],
  eventTimestamp: string
): { name: string; offsetSeconds: number } | null {
  const eventMs = new Date(eventTimestamp).getTime();
  if (!Number.isFinite(eventMs)) return null;
  const eventUnix = Math.floor(eventMs / 1000);
  const withStart = recordings
    .map((r) => {
      const m = r.name.match(/^recording_(\d+)\.avi$/);
      const start = m ? parseInt(m[1], 10) : 0;
      return { ...r, startUnix: start };
    })
    .filter((r) => r.startUnix > 0)
    .sort((a, b) => b.startUnix - a.startUnix);
  const best = withStart.find((r) => r.startUnix <= eventUnix);
  if (!best) return null;
  const offsetSeconds = Math.max(0, eventUnix - best.startUnix);
  return { name: best.name, offsetSeconds };
}
export async function downloadRecordingExport(name: string, format?: 'avi' | 'mp4'): Promise<Blob> {
  const url = format === 'mp4'
    ? `${API_BASE}/recordings/${encodeURIComponent(name)}/export?format=mp4`
    : `${API_BASE}/recordings/${encodeURIComponent(name)}/export`;
  const r = await get(url);
  if (r.status === 403) throw new Error('Forbidden: operator or admin role required');
  if (r.status === 404) throw new Error('Recording not found');
  if (r.status === 503) throw new Error('MP4 conversion unavailable (ffmpeg not available)');
  if (!r.ok) throw new Error('Export failed');
  return r.blob();
}

/** NISTIR 8161-style manifest (metadata + SHA-256) for a recording. */
export type RecordingManifest = {
  name?: string;
  size_bytes?: number;
  created_utc?: string;
  export_sha256?: string;
  [key: string]: unknown;
};
export async function fetchRecordingManifest(name: string): Promise<RecordingManifest> {
  const r = await get(`${API_BASE}/recordings/${encodeURIComponent(name)}/manifest`);
  if (r.status === 403) throw new Error('Forbidden');
  if (r.status === 404) throw new Error('Recording not found');
  if (!r.ok) throw new Error('Failed to fetch manifest');
  return r.json();
}

/** Storage location for recordings and exports (e.g. external drive). */
export type StorageDrive = { path: string; label: string };
export type StorageResponse = {
  path?: string;
  recordings_path?: string;
  available_drives: StorageDrive[];
  can_write?: boolean;
  used_bytes?: number;
  storage_used_bytes?: number;
  recording_count?: number;
  success?: boolean;
  message?: string;
  error?: string;
};
export async function fetchStorage(): Promise<StorageResponse> {
  const r = await get(`${API_BASE}/api/storage`);
  if (!r.ok) throw new Error('Failed to fetch storage');
  return r.json();
}
/** Set recordings/export path. Use null to reset to app default. Admin only. */
export async function setStoragePath(path: string | null): Promise<StorageResponse> {
  const r = await post(`${API_BASE}/api/storage`, { path: path || null });
  if (r.status === 403) throw new Error('Admin role required to change storage location');
  if (r.status === 400) {
    const d = await r.json().catch(() => ({}));
    throw new Error((d as { error?: string }).error || 'Invalid path');
  }
  if (!r.ok) throw new Error('Failed to update storage');
  return r.json();
}

// ---------- API v1 (enterprise / analytics / search) ----------
const API_V1 = `${API_BASE}/api/v1`;

export type AiDataVerifyResult = { verified: number; mismatched: number; total: number };
export async function fetchAiDataVerify(): Promise<AiDataVerifyResult> {
  const r = await get(`${API_V1}/ai_data/verify`);
  if (r.status === 403) throw new Error('Forbidden: operator or admin role required');
  if (!r.ok) throw new Error('Verification failed');
  return r.json();
}

/** Parse raw surveillance log (YOLOv8/Frigate-style). Returns parsed rows and summary. */
export type ParseLogResponse = {
  rows: Record<string, unknown>[];
  columns: string[];
  summary: { rows: number; columns?: string[]; hours_covered?: number };
};
export async function parseLog(logText: string): Promise<ParseLogResponse> {
  const r = await post(`${API_V1}/parse_log`, { log_text: logText });
  if (r.status === 403) throw new Error('Forbidden: viewer or higher role required');
  if (r.status === 503) throw new Error('Parser not available or parse failed');
  if (!r.ok) throw new Error('Parse failed');
  return r.json();
}

/** Parse surveillance log from file (upload). */
export async function parseLogFile(file: File): Promise<ParseLogResponse> {
  const form = new FormData();
  form.append('file', file);
  const r = await fetch(`${API_V1}/parse_log`, {
    ...fetchOpts,
    method: 'POST',
    body: form,
  });
  if (r.status === 403) throw new Error('Forbidden: viewer or higher role required');
  if (r.status === 503) throw new Error('Parser not available or parse failed');
  if (!r.ok) throw new Error('Parse failed');
  return r.json();
}

/** URL for surveillance analysis report (markdown); open in new tab or iframe. */
export function getSurveillanceAnalysisReportUrl(): string {
  return `${API_BASE}/api/v1/surveillance_analysis_report`;
}

/** Saved searches (NIST AU-9). */
export type SavedSearch = { id: number; name: string; params_json: string; created_at: string };
export async function fetchSavedSearches(): Promise<SavedSearch[]> {
  const r = await get(`${API_V1}/saved_searches`);
  if (!r.ok) throw new Error('Failed to fetch saved searches');
  const data = await r.json();
  return data.saved_searches ?? [];
}
export async function createSavedSearch(name: string, params: Record<string, unknown>): Promise<{ id: number; name: string; params: Record<string, unknown>; created_at: string }> {
  const r = await post(`${API_V1}/saved_searches`, { name, params });
  if (!r.ok) throw new Error('Failed to create saved search');
  return r.json();
}
export async function deleteSavedSearch(id: number): Promise<void> {
  const r = await fetch(`${API_V1}/saved_searches/${id}`, { ...fetchOpts, method: 'DELETE' }).then(handle401);
  if (r.status === 404) throw new Error('Not found or not owner');
  if (!r.ok) throw new Error('Failed to delete');
}

/** Incident export bundle manifest (chain of custody for insurance/LE). */
export type IncidentBundleManifest = {
  export_utc: string;
  operator: string;
  system_id: string;
  date_from: string;
  date_to: string;
  retention_days: number;
  recordings: Array<{ name: string; size_bytes: number; created_utc: string }>;
  ai_data_export_url: string;
  purpose: string;
};
export async function fetchIncidentBundle(dateFrom: string, dateTo: string): Promise<{ manifest: IncidentBundleManifest }> {
  const r = await get(`${API_V1}/export/incident_bundle?from=${encodeURIComponent(dateFrom)}&to=${encodeURIComponent(dateTo)}`);
  if (r.status === 403) throw new Error('Export requires admin approval or operator role');
  if (!r.ok) throw new Error('Failed to generate incident bundle');
  return r.json();
}

export type SearchResult = {
  events: Array<{ id: number; event_type: string; camera_id: string | null; site_id?: string; timestamp: string; metadata: string | null; severity: string }>;
  ai_data: Array<{ date: string; time: string; object: string; event: string; scene: string; license_plate: string; crowd_count: number; camera_id?: string }>;
};

export async function searchQuery(q: string, limit?: number): Promise<SearchResult> {
  const r = await post(`${API_V1}/search`, { q, limit: limit ?? 50 });
  if (!r.ok) throw new Error('Search failed');
  return r.json();
}

/** Quick search with filters (date, camera, event type). Uses POST; backend also supports GET with query params. */
export async function searchQueryWithFilters(params: {
  q: string;
  limit?: number;
  date_from?: string;
  date_to?: string;
  camera_id?: string;
  event_type?: string;
}): Promise<SearchResult> {
  const r = await post(`${API_V1}/search`, {
    q: params.q,
    limit: params.limit ?? 50,
    date_from: params.date_from,
    date_to: params.date_to,
    camera_id: params.camera_id,
    event_type: params.event_type,
  });
  if (!r.ok) throw new Error('Search failed');
  return r.json();
}

/** Public map config for Leaflet (tile URL, default center). No auth. */
export type MapConfig = {
  map: {
    tile_url: string;
    default_lat: number;
    default_lon: number;
    default_zoom: number;
    attribution?: string;
  };
};
export async function fetchMapConfig(): Promise<MapConfig> {
  const r = await get(`${API_BASE}/api/v1/config/public`);
  if (!r.ok) throw new Error('Failed to fetch map config');
  return r.json();
}

export type AggregateRow = { date: string; hour: string; event: string; camera_id: string; count: number; total_crowd: number | null };

export async function fetchAggregates(params?: {
  date_from?: string;
  date_to?: string;
  camera_id?: string;
  site_id?: string;
}): Promise<{ aggregates: AggregateRow[]; bucket_hours: number }> {
  const sp = new URLSearchParams();
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  if (params?.camera_id) sp.set('camera_id', params.camera_id);
  if (params?.site_id) sp.set('site_id', params.site_id);
  const r = await get(`${API_V1}/analytics/aggregates?${sp}`);
  if (!r.ok) throw new Error('Failed to fetch analytics');
  return r.json();
}

export type HeatmapBucket = { date: string; hour: string; event_type: string; camera_id: string; count: number };
export async function fetchHeatmap(params?: {
  date_from?: string;
  date_to?: string;
  bucket_hours?: number;
}): Promise<{ heatmap: HeatmapBucket[]; date_from: string; date_to: string; bucket_hours: number }> {
  const sp = new URLSearchParams();
  if (params?.date_from) sp.set('date_from', params.date_from);
  if (params?.date_to) sp.set('date_to', params.date_to);
  if (params?.bucket_hours != null) sp.set('bucket_hours', String(params.bucket_hours));
  const r = await get(`${API_V1}/analytics/heatmap?${sp}`);
  if (!r.ok) throw new Error('Failed to fetch heatmap');
  return r.json();
}

/** Zone dwell: person-seconds per zone per hour (crowd density heatmap). */
export type ZoneDwellBucket = { date: string; hour_bucket: string; camera_id: string; zone_index: number; frame_count: number; person_seconds: number };
export async function fetchZoneDwell(params?: {
  date_from?: string;
  date_to?: string;
  camera_id?: string;
  zone_index?: number;
}): Promise<{ zone_dwell: ZoneDwellBucket[]; date_from: string; date_to: string; interval_seconds: number }> {
  const sp = new URLSearchParams();
  if (params?.date_from) sp.set('date_from', params.date_from ?? '');
  if (params?.date_to) sp.set('date_to', params.date_to ?? '');
  if (params?.camera_id) sp.set('camera_id', params.camera_id);
  if (params?.zone_index != null) sp.set('zone_index', String(params.zone_index));
  const r = await get(`${API_V1}/analytics/zone_dwell?${sp}`);
  if (!r.ok) throw new Error('Failed to fetch zone dwell');
  return r.json();
}

/** Spatial heatmap: binned centroid_nx/ny (camera-view occupancy). */
export type SpatialHeatmapCell = { i: number; j: number; count: number; person_seconds: number };
export async function fetchSpatialHeatmap(params?: {
  date_from?: string;
  date_to?: string;
  camera_id?: string;
  grid_size?: number;
}): Promise<{
  grid_rows: number;
  grid_cols: number;
  cells: SpatialHeatmapCell[];
  date_from: string;
  date_to: string;
  camera_id: string | null;
  interval_seconds: number;
}> {
  const sp = new URLSearchParams();
  if (params?.date_from) sp.set('date_from', params.date_from ?? '');
  if (params?.date_to) sp.set('date_to', params.date_to ?? '');
  if (params?.camera_id) sp.set('camera_id', params.camera_id);
  if (params?.grid_size != null) sp.set('grid_size', String(params.grid_size));
  const r = await get(`${API_V1}/analytics/spatial_heatmap?${sp}`);
  if (!r.ok) throw new Error('Failed to fetch spatial heatmap');
  return r.json();
}

/** World/floor heatmap: binned world_x/world_y (requires homography). Same response shape as spatial. */
export async function fetchWorldHeatmap(params?: {
  date_from?: string;
  date_to?: string;
  camera_id?: string;
  grid_size?: number;
}): Promise<{
  grid_rows: number;
  grid_cols: number;
  cells: SpatialHeatmapCell[];
  date_from: string;
  date_to: string;
  camera_id: string | null;
  interval_seconds: number;
}> {
  const sp = new URLSearchParams();
  if (params?.date_from) sp.set('date_from', params.date_from ?? '');
  if (params?.date_to) sp.set('date_to', params.date_to ?? '');
  if (params?.camera_id) sp.set('camera_id', params.camera_id);
  if (params?.grid_size != null) sp.set('grid_size', String(params.grid_size));
  const r = await get(`${API_V1}/analytics/world_heatmap?${sp}`);
  if (!r.ok) throw new Error('Failed to fetch world heatmap');
  return r.json();
}

/** Vehicle activity: LPR sightings and per-plate summary. */
export type VehicleSighting = { date: string; time: string; timestamp_utc: string; camera_id: string; license_plate: string };
export type VehicleByPlate = { count: number; camera_ids: string[]; first_seen: string; last_seen: string | null };
export async function fetchVehicleActivity(params?: {
  date_from?: string;
  date_to?: string;
  camera_id?: string;
  plate?: string;
}): Promise<{ sightings: VehicleSighting[]; by_plate: Record<string, VehicleByPlate>; date_from: string; date_to: string }> {
  const sp = new URLSearchParams();
  if (params?.date_from) sp.set('date_from', params.date_from ?? '');
  if (params?.date_to) sp.set('date_to', params.date_to ?? '');
  if (params?.camera_id) sp.set('camera_id', params.camera_id);
  if (params?.plate) sp.set('plate', params.plate);
  const r = await get(`${API_V1}/analytics/vehicle_activity?${sp}`);
  if (!r.ok) throw new Error('Failed to fetch vehicle activity');
  return r.json();
}

export type LegalHold = { id: number; resource_type: string; resource_id: string; held_at: string; held_by: string; reason: string | null };
export async function fetchLegalHolds(): Promise<{ holds: LegalHold[] }> {
  const r = await get(`${API_V1}/legal_hold`);
  if (!r.ok) throw new Error('Failed to fetch legal holds');
  return r.json();
}
export async function addLegalHold(resourceType: 'recording' | 'event', resourceId: string, reason?: string): Promise<LegalHold & { message?: string }> {
  const r = await post(`${API_V1}/legal_hold`, { resource_type: resourceType, resource_id: resourceId, reason: reason || '' });
  if (!r.ok) throw new Error('Failed to place legal hold');
  return r.json();
}
export async function removeLegalHold(holdId: number): Promise<void> {
  const r = await fetch(`${API_BASE}/api/v1/legal_hold/${holdId}`, { ...fetchOpts, method: 'DELETE' }).then(handle401);
  if (r.status === 404) throw new Error('Legal hold not found');
  if (!r.ok) throw new Error('Failed to remove legal hold');
}

export type User = { id: number; username: string; role: string };
export async function fetchUsers(): Promise<{ users: User[] }> {
  const r = await get(`${API_V1}/users`);
  if (r.status === 403) throw new Error('Forbidden: admin only');
  if (!r.ok) throw new Error('Failed to fetch users');
  return r.json();
}
export async function fetchUserSites(userId: number): Promise<{ user_id: number; site_ids: string[] }> {
  const r = await get(`${API_V1}/users/${userId}/sites`);
  if (!r.ok) throw new Error('Failed to fetch user sites');
  return r.json();
}
export async function updateUserSites(userId: number, siteIds: string[]): Promise<{ user_id: number; site_ids: string[] }> {
  const r = await put(`${API_V1}/users/${userId}/sites`, { site_ids: siteIds });
  if (!r.ok) throw new Error('Failed to update user sites');
  return r.json();
}
