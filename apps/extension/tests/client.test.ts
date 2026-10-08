import { describe, expect, it } from 'vitest'
import { checkHealth } from '../src/service/client'

function okFetch(body: unknown): typeof fetch {
  return (async () =>
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })) as unknown as typeof fetch
}

function failingFetch(message: string): typeof fetch {
  return (async () => {
    throw new TypeError(message)
  }) as unknown as typeof fetch
}

describe('checkHealth', () => {
  it('reports connected with the service version', async () => {
    const result = await checkHealth('http://127.0.0.1:8765', {
      fetchImpl: okFetch({ status: 'ok', version: '0.1.0' }),
    })
    expect(result.status).toBe('connected')
    expect(result.version).toBe('0.1.0')
    expect(result.baseUrl).toBe('http://127.0.0.1:8765')
  })

  it('surfaces a degraded service without calling it offline', async () => {
    const result = await checkHealth('http://127.0.0.1:8765', {
      fetchImpl: okFetch({ status: 'degraded', version: '0.1.0' }),
    })
    expect(result.status).toBe('connected')
    expect(result.detail).toContain('degraded')
  })

  it('reports offline when the service is not listening', async () => {
    const result = await checkHealth('http://127.0.0.1:8765', {
      fetchImpl: failingFetch('Failed to fetch'),
    })
    expect(result.status).toBe('offline')
    expect(result.detail).toContain('Could not reach the local service')
  })

  it('reports offline on a non-2xx answer', async () => {
    const result = await checkHealth('http://127.0.0.1:8765', {
      fetchImpl: (async () =>
        new Response('', {
          status: 503,
          statusText: 'Service Unavailable',
        })) as unknown as typeof fetch,
    })
    expect(result.status).toBe('offline')
    expect(result.detail).toContain('503')
  })

  it('refuses a non-loopback address without touching the network', async () => {
    let called = false
    const result = await checkHealth('http://example.com', {
      fetchImpl: (async () => {
        called = true
        return new Response('{}')
      }) as unknown as typeof fetch,
    })
    expect(result.status).toBe('offline')
    expect(result.baseUrl).toBe('')
    expect(called).toBe(false)
  })

  it('times out instead of hanging when the service never answers', async () => {
    const result = await checkHealth('http://127.0.0.1:8765', {
      timeoutMs: 10,
      fetchImpl: ((_url: string, init?: RequestInit) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => reject(new Error('aborted')))
        })) as unknown as typeof fetch,
    })
    expect(result.status).toBe('offline')
  })

  it('retries once when the first attempt aborts and then connects', async () => {
    let calls = 0
    const fetchImpl = ((_url: string, init?: RequestInit) => {
      calls += 1
      if (calls === 1) {
        return new Promise((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => reject(new Error('aborted')))
        })
      }
      return Promise.resolve(
        new Response(JSON.stringify({ status: 'ok', version: '0.1.0' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    }) as unknown as typeof fetch
    const result = await checkHealth('http://127.0.0.1:8765', {
      timeoutMs: 10,
      fetchImpl,
    })
    expect(result.status).toBe('connected')
    expect(calls).toBe(2)
  })

  it('does not retry an HTTP error answer', async () => {
    let calls = 0
    const result = await checkHealth('http://127.0.0.1:8765', {
      fetchImpl: (async () => {
        calls += 1
        return new Response('', { status: 503, statusText: 'Service Unavailable' })
      }) as unknown as typeof fetch,
    })
    expect(result.status).toBe('offline')
    expect(result.detail).toContain('503')
    expect(calls).toBe(1)
  })

  it('reports the last failure after two aborted attempts', async () => {
    let calls = 0
    const result = await checkHealth('http://127.0.0.1:8765', {
      timeoutMs: 10,
      fetchImpl: ((_url: string, init?: RequestInit) => {
        calls += 1
        return new Promise((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => reject(new Error(`aborted-${calls}`)))
        })
      }) as unknown as typeof fetch,
    })
    expect(result.status).toBe('offline')
    expect(result.detail).toContain('aborted-2')
    expect(calls).toBe(2)
  })
})
