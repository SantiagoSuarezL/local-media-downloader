// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../src/lib/api', () => ({
  api: { getJob: vi.fn() },
}))

type NotifyModule = typeof import('../src/lib/notify')
type LiveModule = typeof import('../src/lib/live')
type ApiModule = typeof import('../src/lib/api')

class FakeNotification {
  static instances: { title: string; body: string }[] = []

  static permission: NotificationPermission = 'default'

  static requestPermission: () => Promise<NotificationPermission> = async () => 'denied'

  constructor(title: string, options?: NotificationOptions) {
    FakeNotification.instances.push({ title, body: options?.body ?? '' })
  }
}

let notifyMod: NotifyModule
let liveMod: LiveModule
let getJob: ReturnType<typeof vi.fn>

function liveEntry(state: string): Record<string, import('../src/lib/live').LiveJob> {
  return {
    'job-1': {
      job_id: 'job-1',
      state,
      stage: null,
      percentage: 100,
      downloadedBytes: null,
      totalBytes: null,
      speed: null,
      eta: null,
    },
  }
}

beforeEach(async () => {
  vi.resetModules()
  FakeNotification.instances = []
  FakeNotification.permission = 'default'
  FakeNotification.requestPermission = async () => 'denied'
  vi.stubGlobal('Notification', FakeNotification)
  window.localStorage.clear()
  notifyMod = await import('../src/lib/notify')
  liveMod = await import('../src/lib/live')
  const apiMod: ApiModule = await import('../src/lib/api')
  getJob = apiMod.api.getJob as unknown as ReturnType<typeof vi.fn>
  getJob.mockResolvedValue({ title: 'Some video', output_path: '/dl/v.mp4' })
})

describe('notificationsEnabled', () => {
  it('is opt-in: off until the user enables it', () => {
    expect(notifyMod.notificationsEnabled()).toBe(false)
    notifyMod.setNotificationsEnabled(true)
    expect(notifyMod.notificationsEnabled()).toBe(true)
    notifyMod.setNotificationsEnabled(false)
    expect(notifyMod.notificationsEnabled()).toBe(false)
  })
})

describe('requestNotificationPermission', () => {
  it('fails closed without the Notification API', async () => {
    vi.unstubAllGlobals()
    expect('Notification' in window).toBe(false)
    expect(await notifyMod.requestNotificationPermission()).toBe(false)
  })

  it('passes through an already-granted permission', async () => {
    FakeNotification.permission = 'granted'
    expect(await notifyMod.requestNotificationPermission()).toBe(true)
  })

  it('asks once when the permission is undecided', async () => {
    FakeNotification.requestPermission = async () => 'granted'
    expect(await notifyMod.requestNotificationPermission()).toBe(true)
    FakeNotification.requestPermission = async () => 'denied'
    expect(await notifyMod.requestNotificationPermission()).toBe(false)
  })
})

describe('startJobNotifications', () => {
  it('announces a completed job with its title and output path', async () => {
    FakeNotification.permission = 'granted'
    notifyMod.setNotificationsEnabled(true)
    notifyMod.startJobNotifications()
    liveMod.live.set(liveEntry('COMPLETED'))
    await vi.waitFor(() => expect(FakeNotification.instances).toHaveLength(1))
    expect(getJob).toHaveBeenCalledWith('job-1')
    expect(FakeNotification.instances[0]).toEqual({
      title: 'Some video',
      body: 'Download complete: /dl/v.mp4',
    })
  })

  it('announces a failure with the backend error code', async () => {
    FakeNotification.permission = 'granted'
    notifyMod.setNotificationsEnabled(true)
    notifyMod.startJobNotifications()
    getJob.mockResolvedValue({ title: 'Clip', error_code: 'NETWORK_ERROR' })
    liveMod.live.set(liveEntry('FAILED'))
    await vi.waitFor(() => expect(FakeNotification.instances).toHaveLength(1))
    expect(FakeNotification.instances[0].body).toBe('Download failed: NETWORK_ERROR')
  })

  it('stays silent for non-terminal states', async () => {
    FakeNotification.permission = 'granted'
    notifyMod.setNotificationsEnabled(true)
    notifyMod.startJobNotifications()
    liveMod.live.set(liveEntry('DOWNLOADING'))
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(FakeNotification.instances).toHaveLength(0)
    expect(getJob).not.toHaveBeenCalled()
  })

  it('notifies once per terminal transition, not per frame', async () => {
    FakeNotification.permission = 'granted'
    notifyMod.setNotificationsEnabled(true)
    notifyMod.startJobNotifications()
    liveMod.live.set(liveEntry('COMPLETED'))
    await vi.waitFor(() => expect(FakeNotification.instances).toHaveLength(1))
    liveMod.live.set(liveEntry('COMPLETED'))
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(FakeNotification.instances).toHaveLength(1)
  })

  it('still notifies with the id when the job row is already gone', async () => {
    FakeNotification.permission = 'granted'
    notifyMod.setNotificationsEnabled(true)
    notifyMod.startJobNotifications()
    getJob.mockRejectedValue(new Error('gone'))
    liveMod.live.set(liveEntry('FAILED'))
    await vi.waitFor(() => expect(FakeNotification.instances).toHaveLength(1))
    expect(FakeNotification.instances[0].body).toBe('Job job-1 failed')
  })

  it('stays silent when the user opted out', async () => {
    FakeNotification.permission = 'granted'
    notifyMod.setNotificationsEnabled(false)
    notifyMod.startJobNotifications()
    liveMod.live.set(liveEntry('COMPLETED'))
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(FakeNotification.instances).toHaveLength(0)
  })

  it('stays silent without OS permission', async () => {
    FakeNotification.permission = 'denied'
    notifyMod.setNotificationsEnabled(true)
    notifyMod.startJobNotifications()
    liveMod.live.set(liveEntry('COMPLETED'))
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(FakeNotification.instances).toHaveLength(0)
  })
})
