/**
 * Health probe against the local service.
 *
 * The popup must never hang: a service that is down (or a port that is wrong)
 * has to render "Offline" quickly, so the probe carries its own timeout. A
 * network failure is an expected state here, not an exception to propagate.
 */

import type { HealthDto } from '@lmd/contracts'
import { normalizeServiceUrl } from '../lib/handoff'

export const DEFAULT_TIMEOUT_MS = 1500

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
        body.status === 'degraded' ? 'Connected, but the service reports degraded.' : 'Connected.',
      version: body.version,
      baseUrl: base,
    }
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error)
    return {
      status: 'offline',
      detail: `Could not reach the local service (${reason}).`,
      baseUrl: base,
    }
  } finally {
    clearTimeout(timer)
  }
}
