/**
 * Health probe against the local service.
 *
 * The popup must never hang: a service that is down (or a port that is wrong)
 * has to render "Offline" quickly, so the probe carries its own timeout. A
 * network failure is an expected state here, not an exception to propagate.
 *
 * One retry on thrown errors only (abort, connection refused): the health
 * endpoint re-runs tool detection when its 5 s cache expires — four sequential
 * subprocess boots plus the extractor check — and on a loaded machine that
 * takes several seconds while the service is fine. An HTTP answer, even an
 * error status, is definitive and is never retried.
 *
 * The timeout only bites when the service is alive but slow: a dead service
 * refuses the connection in milliseconds, so a generous budget never hangs
 * the popup on the common down case.
 */

import type { HealthDto } from '@lmd/contracts'
import { normalizeServiceUrl } from '../lib/handoff'

export const DEFAULT_TIMEOUT_MS = 6000

/** Attempts per probe: first try plus one retry on transient failures. */
const MAX_ATTEMPTS = 2

export type ConnectionStatus = 'connected' | 'offline'

export interface HealthResult {
  status: ConnectionStatus
  /** User-facing explanation, always populated for `offline`. */
  detail: string
  /** Service-reported version when the probe succeeded. */
  version?: string
  /** The probe hit this base URL (normalized). */
  baseUrl: string
}

export async function checkHealth(
  serviceUrl: string,
  {
    timeoutMs = DEFAULT_TIMEOUT_MS,
    fetchImpl = fetch,
  }: {
    timeoutMs?: number
    fetchImpl?: typeof fetch
  } = {},
): Promise<HealthResult> {
  const base = normalizeServiceUrl(serviceUrl)
  if (base === null) {
    return {
      status: 'offline',
      detail: 'The service address must be a loopback URL (127.0.0.1, localhost or [::1]).',
      baseUrl: '',
    }
  }

  let lastDetail = 'Could not reach the local service.'
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    try {
      const response = await fetchImpl(`${base}/api/v1/health`, {
        method: 'GET',
        cache: 'no-store',
        signal: controller.signal,
      })
      if (!response.ok) {
        return {
          status: 'offline',
          detail: `The service answered ${response.status} ${response.statusText}.`,
          baseUrl: base,
        }
      }
      const body = (await response.json()) as Partial<HealthDto>
      return {
        status: 'connected',
        detail:
          body.status === 'degraded'
            ? 'Connected, but the service reports degraded.'
            : 'Connected.',
        version: body.version,
        baseUrl: base,
      }
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error)
      lastDetail = `Could not reach the local service (${reason}).`
    } finally {
      clearTimeout(timer)
    }
  }
  return { status: 'offline', detail: lastDetail, baseUrl: base }
}
