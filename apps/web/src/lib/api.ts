import type {
  CreateJobRequest,
  HealthDto,
  JobDto,
  JobListResponse,
  MediaInfoDto,
  SettingsDto,
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

export const api = {
  health: () => request<HealthDto>('/api/v1/health'),
  settings: () => request<SettingsDto>('/api/v1/settings'),
  resolve: (url: string) =>
    request<MediaInfoDto>('/api/v1/resolve', { method: 'POST', body: JSON.stringify({ url }) }),
  createJob: (payload: CreateJobRequest) =>
    request<JobDto>('/api/v1/jobs', { method: 'POST', body: JSON.stringify(payload) }),
  listJobs: () => request<JobListResponse>('/api/v1/jobs'),
  getJob: (id: string) => request<JobDto>(`/api/v1/jobs/${id}`),
  cancelJob: (id: string) => request<JobDto>(`/api/v1/jobs/${id}/cancel`, { method: 'POST' }),
  eventsUrl: '/api/v1/events',
}
