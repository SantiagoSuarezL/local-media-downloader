// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../src/lib/api'
import { baseIntent } from '../src/lib/presets'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function setToken(token: string | null): void {
  document.head.innerHTML = token === null ? '' : `<meta name="lmd-token" content="${token}">`
}

afterEach(() => {
  vi.unstubAllGlobals()
  document.head.innerHTML = ''
})

function stubFetch(respond: () => Response): {
  calls: { url: string; init: RequestInit | undefined }[]
} {
  const calls: { url: string; init: RequestInit | undefined }[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init })
      return respond()
    }),
  )
  return { calls }
}

function headersOf(call: { init: RequestInit | undefined }): Record<string, string> {
  return (call.init?.headers ?? {}) as Record<string, string>
}

describe('api token handling', () => {
  it('sends the shell token on every call', async () => {
    setToken('tok123')
    const { calls } = stubFetch(() => jsonResponse({ status: 'ok' }))
    await api.settings()
    expect(calls).toHaveLength(1)
    expect(headersOf(calls[0])['X-LMD-Token']).toBe('tok123')
  })

  it('omits the header when the shell carries no token', async () => {
    setToken(null)
    const { calls } = stubFetch(() => jsonResponse({ status: 'ok' }))
    await api.settings()
    expect(headersOf(calls[0])['X-LMD-Token']).toBeUndefined()
  })

  it('always sends JSON content type', async () => {
    setToken('tok123')
    const { calls } = stubFetch(() => jsonResponse({ status: 'ok' }))
    await api.settings()
    expect(headersOf(calls[0])['Content-Type']).toBe('application/json')
  })
})

describe('api error handling', () => {
  it('prefers the backend error message over the HTTP status text', async () => {
    setToken('t')
    stubFetch(
      () =>
        new Response(JSON.stringify({ error: { code: 'UNAUTHORIZED', message: 'nope' } }), {
          status: 401,
          statusText: 'Unauthorized',
        }),
    )
    await expect(api.settings()).rejects.toThrow('nope')
  })

  it('falls back to the status text when the body is not JSON', async () => {
    setToken('t')
    stubFetch(() => new Response('<html>proxy error</html>', { status: 502 }))
    await expect(api.settings()).rejects.toThrow('502')
  })

  it('falls back to the status text when the envelope has no message', async () => {
    setToken('t')
    stubFetch(
      () =>
        new Response(JSON.stringify({ error: { code: 'X' } }), {
          status: 422,
          statusText: 'Unprocessable Entity',
        }),
    )
    await expect(api.settings()).rejects.toThrow('422')
  })
})

describe('api endpoints', () => {
  it('hits the right paths and methods', async () => {
    setToken('t')
    const { calls } = stubFetch(() => jsonResponse({}))
    await api.health()
    await api.resolve('https://example.com/v')
    await api.createJob({ url: 'https://example.com/v', intent: baseIntent() })
    await api.getJob('job-1')
    await api.cancelJob('job-1')
    await api.retryJob('job-1')
    await api.setPriority('job-1', -50)
    await api.updateSettings({ history_retention_days: 7 })
    await api.runCleanup()
    const methods = calls.map((call) => [call.url, (call.init?.method ?? 'GET').toUpperCase()])
    expect(methods).toEqual([
      ['/api/v1/health', 'GET'],
      ['/api/v1/resolve', 'POST'],
      ['/api/v1/jobs', 'POST'],
      ['/api/v1/jobs/job-1', 'GET'],
      ['/api/v1/jobs/job-1/cancel', 'POST'],
      ['/api/v1/jobs/job-1/retry', 'POST'],
      ['/api/v1/jobs/job-1/priority', 'POST'],
      ['/api/v1/settings', 'PATCH'],
      ['/api/v1/maintenance/cleanup', 'POST'],
    ])
  })

  it('serializes create payloads as JSON', async () => {
    setToken('t')
    const { calls } = stubFetch(() => jsonResponse({}))
    const intent = baseIntent()
    await api.createJob({ url: 'https://example.com/v', intent })
    expect(JSON.parse(calls[0].init?.body as string)).toEqual({
      url: 'https://example.com/v',
      intent,
    })
  })

  it('builds the listJobs query from limit, cursor and states', async () => {
    setToken('t')
    const { calls } = stubFetch(() => jsonResponse({ jobs: [], next_cursor: null }))
    await api.listJobs({ limit: 25, cursor: 'abc', states: ['QUEUED', 'FAILED'] })
    const url = new URL(calls[0].url, 'http://127.0.0.1')
    expect(url.pathname).toBe('/api/v1/jobs')
    expect(url.searchParams.get('limit')).toBe('25')
    expect(url.searchParams.get('cursor')).toBe('abc')
    expect(url.searchParams.get('states')).toBe('QUEUED,FAILED')
  })

  it('omits empty listJobs options instead of sending blanks', async () => {
    setToken('t')
    const { calls } = stubFetch(() => jsonResponse({ jobs: [], next_cursor: null }))
    await api.listJobs()
    expect(calls[0].url).toBe('/api/v1/jobs')
  })

  it('exposes the SSE url the EventSource connects to', () => {
    expect(api.eventsUrl).toBe('/api/v1/events')
  })
})

describe('api batch', () => {
  it('posts items in order with one shared intent', async () => {
    setToken('t')
    const { calls } = stubFetch(() => jsonResponse({ results: [] }))
    const intent = baseIntent()
    await api.createBatch({
      items: [
        { url: 'https://example.com/1', intent },
        { url: 'https://example.com/2', intent, priority: 5 },
      ],
    })
    expect(calls[0].url).toBe('/api/v1/jobs/batch')
    expect(JSON.parse(calls[0].init?.body as string)).toEqual({
      items: [
        { url: 'https://example.com/1', intent },
        { url: 'https://example.com/2', intent, priority: 5 },
      ],
    })
  })
})
