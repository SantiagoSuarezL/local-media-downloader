/**
 * Handoff logic: what the popup may send to the local service, and where.
 *
 * Two invariants live here, both security-relevant:
 *
 * 1. The extension only ever talks to **loopback**. A media URL pasted into the
 *    popup must never be handed to a remote "service", so the base URL is
 *    validated against loopback hosts before use or storage.
 * 2. Only `http:`/`https:` page URLs are candidates. `chrome://`, `file://`,
 *    `javascript:` and `data:` pages are refused: the local service would
 *    reject them anyway, and the popup should say so instead of failing later.
 */

export const DEFAULT_SERVICE_URL = 'http://127.0.0.1:8765'

export const SERVICE_URL_KEY = 'lmd.serviceUrl'

const LOOPBACK_HOSTS = new Set(['127.0.0.1', 'localhost', '[::1]', '::1'])

/** Matches the API bound size (TECHNICAL_SPEC §5): longer URLs are refused. */
export const MAX_URL_LENGTH = 2048

export interface Validation {
  ok: boolean
  reason?: string
}

/**
 * Normalize a user-entered service URL, or return null when it is not a
 * loopback http(s) endpoint. Ports are preserved: the service port is
 * configurable (LMD_PORT) and the default may not apply.
 */
export function normalizeServiceUrl(raw: string): string | null {
  const trimmed = raw.trim()
  if (trimmed === '') {
    return null
  }
  let parsed: URL
  try {
    parsed = new URL(trimmed)
  } catch {
    return null
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    return null
  }
  if (!LOOPBACK_HOSTS.has(parsed.hostname)) {
    return null
  }
  // Only origin matters: the popup appends its own paths.
  return parsed.origin
}

export function isLoopbackServiceUrl(raw: string): boolean {
  return normalizeServiceUrl(raw) !== null
}

/**
 * Decide whether a page URL is worth offering for download. Failing early with
 * a specific reason keeps the popup honest about *why* a page is unsupported.
 */
export function validateMediaUrl(raw: string | undefined): Validation {
  if (!raw || raw.trim() === '') {
    return { ok: false, reason: 'This page has no URL to send.' }
  }
  const trimmed = raw.trim()
  if (trimmed.length > MAX_URL_LENGTH) {
    return { ok: false, reason: 'The page URL is too long to send.' }
  }
  let parsed: URL
  try {
    parsed = new URL(trimmed)
  } catch {
    return { ok: false, reason: 'The page URL could not be parsed.' }
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    return {
      ok: false,
      reason: `Only http and https pages can be sent (this page is ${parsed.protocol}).`,
    }
  }
  return { ok: true }
}

/**
 * Build the dashboard deep link. The URL travels as a query parameter so the
 * dashboard can prefill Resolve without a routing library, and `URL` does the
 * encoding so a URL with `&`/`#` cannot break the parameter.
 */
export function buildDashboardUrl(serviceUrl: string, mediaUrl: string): string {
  const base = normalizeServiceUrl(serviceUrl) ?? DEFAULT_SERVICE_URL
  return `${base}/?url=${encodeURIComponent(mediaUrl)}`
}
