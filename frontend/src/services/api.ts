import type {
  AppSettings,
  EnvironmentDiagnostics,
  JobRecord,
  MediaFileItem,
  MediaProbeResponse,
  MetadataInspection,
} from '../types';

const API_BASE = '/api';

async function requestJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data?.detail || data?.message || `HTTP ${response.status}`;
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return data as T;
}

export const api = {
  getDashboard: () =>
    requestJson<{
      stats: {
        total_jobs: number;
        total_downloads: number;
        completed_jobs: number;
        active_jobs: number;
        failed_jobs: number;
        storage_used_bytes: number;
        total_files: number;
        disk_usage: { total_bytes: number; used_bytes: number; free_bytes: number };
      };
      recent_jobs: JobRecord[];
      diagnostics: EnvironmentDiagnostics;
    }>('/dashboard'),

  probeUrl: (url: string) =>
    requestJson<MediaProbeResponse>('/downloads/probe', {
      method: 'POST',
      body: JSON.stringify({ url }),
    }),

  enqueueDownloads: (payload: Record<string, unknown>) =>
    requestJson<{ jobs: JobRecord[]; count: number }>('/downloads/enqueue', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  listJobs: () => requestJson<{ jobs: JobRecord[] }>('/downloads/jobs'),

  cancelJob: (jobId: string) =>
    requestJson<{ job: JobRecord }>(`/downloads/jobs/${jobId}/cancel`, { method: 'POST' }),

  retryJob: (jobId: string) =>
    requestJson<{ job: JobRecord }>(`/downloads/jobs/${jobId}/retry`, { method: 'POST' }),

  deleteJob: (jobId: string) =>
    requestJson<{ deleted: boolean; id: string }>(`/downloads/jobs/${jobId}`, { method: 'DELETE' }),

  clearCompletedJobs: () =>
    requestJson<{ cleared_count: number }>('/downloads/jobs/clear-completed', { method: 'POST' }),

  enqueueAudioExtract: (payload: Record<string, unknown>) =>
    requestJson<{ job: JobRecord }>('/conversions/audio-extract', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  enqueueVideoConvert: (payload: Record<string, unknown>) =>
    requestJson<{ job: JobRecord }>('/conversions/video-convert', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  enqueueAudioConvert: (payload: Record<string, unknown>) =>
    requestJson<{ job: JobRecord }>('/conversions/audio-convert', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  inspectMetadata: (source_path: string) =>
    requestJson<MetadataInspection>('/conversions/metadata/inspect', {
      method: 'POST',
      body: JSON.stringify({ source_path }),
    }),

  cleanMetadata: (payload: Record<string, unknown>) =>
    requestJson<{
      source_path: string;
      output_path: string;
      output_filename: string;
      before: MetadataInspection;
      after: MetadataInspection;
      removed_tag_count: number;
      disclaimer: string;
    }>('/conversions/metadata/clean?sync=true', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  listFiles: (params: { search?: string; media_type?: string; sort_by?: string; sort_desc?: boolean }) => {
    const q = new URLSearchParams();
    if (params.search) q.set('search', params.search);
    if (params.media_type) q.set('media_type', params.media_type);
    if (params.sort_by) q.set('sort_by', params.sort_by);
    if (params.sort_desc !== undefined) q.set('sort_desc', String(params.sort_desc));
    return requestJson<{
      files: MediaFileItem[];
      total_count: number;
      library_used_bytes: number;
      disk_usage: { total_bytes: number; used_bytes: number; free_bytes: number };
      allowed_directories: string[];
    }>(`/files?${q.toString()}`);
  },

  uploadLocalFile: async (file: File) => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API_BASE}/files/upload`, { method: 'POST', body: form });
    if (!res.ok) throw new Error('File upload failed');
    return (await res.json()) as { filename: string; path: string; size_bytes: number };
  },

  renameFile: (path: string, new_name: string) =>
    requestJson<{ old_path: string; new_path: string; new_name: string }>('/files/rename', {
      method: 'POST',
      body: JSON.stringify({ path, new_name }),
    }),

  deleteFile: (path: string) =>
    requestJson<{ deleted_path: string; filename: string }>(
      `/files?path=${encodeURIComponent(path)}`,
      { method: 'DELETE' }
    ),

  openFileInOs: (path: string, reveal_in_folder = false) =>
    requestJson<{ opened: boolean; path: string }>('/files/open', {
      method: 'POST',
      body: JSON.stringify({ path, reveal_in_folder }),
    }),

  getSettings: () =>
    requestJson<{ settings: AppSettings; diagnostics: EnvironmentDiagnostics }>('/settings'),

  updateSettings: (payload: Partial<AppSettings>) =>
    requestJson<{ settings: AppSettings; diagnostics: EnvironmentDiagnostics }>('/settings', {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
};
