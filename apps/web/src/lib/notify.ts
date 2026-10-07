import { api } from './api'
import { live } from './live'

const STORAGE_KEY = 'lmd-notify-enabled'

const TERMINAL = ['COMPLETED', 'FAILED', 'CANCELLED']

/**
 * Desktop notifications on job completion/failure (Phase 12), with no
 * dependency: the dashboard is already open on the same machine, so the
 * browser Notification API is the delivery channel. Opt-in, persisted in
 * localStorage; the SSE stream already carries the state transitions.
 */
export function notificationsEnabled(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export function setNotificationsEnabled(enabled: boolean): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, enabled ? '1' : '0')
  } catch {
    // private mode: the toggle just does not persist
  }
}

export async function requestNotificationPermission(): Promise<boolean> {
  if (!('Notification' in window)) {
    return false
  }
  if (Notification.permission === 'granted') {
    return true
  }
  return (await Notification.requestPermission()) === 'granted'
}

let started = false
const seen = new Map<string, string | null>()

export function startJobNotifications(): void {
  if (started || !('Notification' in window)) {
    return
  }
  started = true
  live.subscribe((current) => {
    if (!notificationsEnabled() || Notification.permission !== 'granted') {
      return
    }
    for (const [jobId, entry] of Object.entries(current)) {
      const previous = seen.get(jobId)
      seen.set(jobId, entry.state)
      if (entry.state && TERMINAL.includes(entry.state) && previous !== entry.state) {
        void announce(jobId, entry.state)
      }
    }
  })
}

async function announce(jobId: string, state: string): Promise<void> {
  let title: string = 'Local Media Downloader'
  let body: string
  try {
    const job = await api.getJob(jobId)
    title = job.title ?? 'Local Media Downloader'
    body =
      state === 'COMPLETED'
        ? `Download complete${job.output_path ? `: ${job.output_path}` : ''}`
        : state === 'FAILED'
          ? `Download failed${job.error_code ? `: ${job.error_code}` : ''}`
          : `Job ${state.toLowerCase()}`
  } catch {
    // the job row may already be cleaned up; still notify with the id
    body = `Job ${jobId.slice(0, 8)} ${state.toLowerCase()}`
  }
  try {
    new Notification(title, { body })
  } catch {
    // notifications blocked after all: stay silent
  }
}
