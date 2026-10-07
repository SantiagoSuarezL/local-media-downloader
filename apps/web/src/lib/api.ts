import type {
  BatchRequest,
  BatchResponse,
  CleanupReport,
  CreateJobRequest,
  HealthDto,
  JobDto,
  JobListResponse,
  MediaInfoDto,
  SettingsDto,
  SettingsUpdate,
} from '@lmd/contracts'

/**
 * Local API token (Phase 10). The service injects it into the shell it serves,
 * so a same-origin dashboard can authenticate without a login step. Health is
 * intentionally public, so no token is needed for the extension's indicator.
 */
const TOKEN_HEADER = 'X-LMD-Token'

function authToken(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="lmd-token"]')?.content ?? ''
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((init?.headers as Record<string, string> | undefined) ?? {}),
  }
  const token = authToken()
  if (token) {
    headers[TOKEN_HEADER] = token
  }
  const response = await fetch(path, { ...init, headers })
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const body = (await response.json()) as { error?: { code?: string; message?: string } }
      if (body?.error?.message) {
        message = body.error.message
      }
    } catch {
      // keep the HTTP status message
    }
    throw new Error(message)
  }
  return (await response.json()) as T
}

export interface ListJobsOptions {
  limit?: number
  cursor?: string | null
  states?: string[]
}

export const api = {
  health: () => request<HealthDto>('/api/v1/health'),
  settings: () => request<SettingsDto>('/api/v1/settings'),
  updateSettings: (payload: SettingsUpdate) =>
    request<SettingsDto>('/api/v1/settings', { method: 'PATCH', body: JSON.stringify(payload) }),
  resolve: (url: string) =>
    request<MediaInfoDto>('/api/v1/resolve', { method: 'POST', body: JSON.stringify({ url }) }),
  createJob: (payload: CreateJobRequest) =>
    request<JobDto>('/api/v1/jobs', { method: 'POST', body: JSON.stringify(payload) }),
  createBatch: (payload: BatchRequest) =>
    request<BatchResponse>('/api/v1/jobs/batch', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listJobs: (options: ListJobsOptions = {}) => {
    const params = new URLSearchParams()
    if (options.limit != null) {
      params.set('limit', String(options.limit))
    }
    if (options.cursor) {
      params.set('cursor', options.cursor)
    }
    if (options.states?.length) {
      params.set('states', options.states.join(','))
    }
    const query = params.toString()
    return request<JobListResponse>(`/api/v1/jobs${query ? `?${query}` : ''}`)
  },
  getJob: (id: string) => request<JobDto>(`/api/v1/jobs/${id}`),
  cancelJob: (id: string) => request<JobDto>(`/api/v1/jobs/${id}/cancel`, { method: 'POST' }),
  retryJob: (id: string) => request<JobDto>(`/api/v1/jobs/${id}/retry`, { method: 'POST' }),
  setPriority: (id: string, priority: number) =>
    request<JobDto>(`/api/v1/jobs/${id}/priority`, {
      method: 'POST',
      body: JSON.stringify({ priority }),
    }),
  runCleanup: () => request<CleanupReport>('/api/v1/maintenance/cleanup', { method: 'POST' }),
  eventsUrl: '/api/v1/events',
}
