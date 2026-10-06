import { describe, expect, it } from 'vitest'
import {
  DEFAULT_SERVICE_URL,
  buildDashboardUrl,
  isLoopbackServiceUrl,
  normalizeServiceUrl,
  validateMediaUrl,
} from '../src/lib/handoff'

describe('normalizeServiceUrl', () => {
  it('accepts loopback http endpoints and keeps the port', () => {
    expect(normalizeServiceUrl('http://127.0.0.1:8765')).toBe('http://127.0.0.1:8765')
    expect(normalizeServiceUrl('http://localhost:9000')).toBe('http://localhost:9000')
    expect(normalizeServiceUrl('  http://127.0.0.1:8765/  ')).toBe('http://127.0.0.1:8765')
  })

  it('drops any path so only the origin is stored', () => {
    expect(normalizeServiceUrl('http://127.0.0.1:8765/api/v1/health')).toBe('http://127.0.0.1:8765')
  })

  it('refuses anything that is not loopback', () => {
    // A remote "service" must never receive the user's media URLs.
    expect(normalizeServiceUrl('http://example.com')).toBeNull()
    expect(normalizeServiceUrl('https://lmd.example.com:8765')).toBeNull()
    expect(normalizeServiceUrl('http://127.0.0.1.evil.com')).toBeNull()
    expect(normalizeServiceUrl('http://127.0.0.2:8765')).toBeNull()
  })

  it('refuses non-http schemes and garbage', () => {
    expect(normalizeServiceUrl('file:///etc/passwd')).toBeNull()
    expect(normalizeServiceUrl('javascript:alert(1)')).toBeNull()
    expect(normalizeServiceUrl('ws://127.0.0.1:8765')).toBeNull()
    expect(normalizeServiceUrl('')).toBeNull()
    expect(normalizeServiceUrl('not a url')).toBeNull()
  })

  it('exposes the same predicate for the settings UI', () => {
    expect(isLoopbackServiceUrl(DEFAULT_SERVICE_URL)).toBe(true)
    expect(isLoopbackServiceUrl('http://10.0.0.5:8765')).toBe(false)
  })
})

describe('validateMediaUrl', () => {
  it('accepts ordinary http(s) pages', () => {
    expect(validateMediaUrl('https://example.com/watch?v=1')).toEqual({ ok: true })
    expect(validateMediaUrl(' http://example.com/a ')).toEqual({ ok: true })
  })

  it('refuses browser-internal and dangerous schemes with a reason', () => {
    for (const url of [
      'chrome://extensions',
      'file:///C:/Users/me/video.mp4',
      'data:text/html,<h1>hi</h1>',
      'javascript:alert(1)',
      'about:blank',
    ]) {
      const result = validateMediaUrl(url)
      expect(result.ok).toBe(false)
      expect(result.reason).toBeTruthy()
    }
  })

  it('refuses empty and over-long URLs', () => {
    expect(validateMediaUrl(undefined).ok).toBe(false)
    expect(validateMediaUrl('   ').ok).toBe(false)
    expect(validateMediaUrl(`https://example.com/${'a'.repeat(3000)}`).ok).toBe(false)
  })
})

describe('buildDashboardUrl', () => {
  it('carries the media URL as an encoded parameter', () => {
    const link = buildDashboardUrl(
      'http://127.0.0.1:8765',
      'https://example.com/watch?v=1&list=2#frag',
    )
    const parsed = new URL(link)
    expect(parsed.origin).toBe('http://127.0.0.1:8765')
    expect(parsed.pathname).toBe('/')
    // The fragment/query of the media URL must not leak into the dashboard.
    expect(parsed.searchParams.get('url')).toBe('https://example.com/watch?v=1&list=2#frag')
    expect(link).not.toContain('#frag')
  })

  it('falls back to the default service when the address is not loopback', () => {
    const link = buildDashboardUrl('http://evil.example.com', 'https://example.com/v')
    expect(link.startsWith(DEFAULT_SERVICE_URL)).toBe(true)
  })
})
