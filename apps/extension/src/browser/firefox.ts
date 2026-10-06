import type { ActiveTab, BrowserBridge, KeyValueStore } from './types'

const ERROR_NO_ACTIVE_TAB = 'No active tab available'
const ERROR_TABS_PERMISSION = 'The activeTab permission was not granted'

export class FirefoxBridge implements BrowserBridge {
  readonly name = 'firefox' as const

  async getActiveTab(): Promise<ActiveTab> {
    const [tab] = await browser.tabs.query({ active: true, currentWindow: true })
    if (!tab) {
      throw new Error(ERROR_NO_ACTIVE_TAB)
    }
    if (tab.url === undefined) {
      throw new Error(ERROR_TABS_PERMISSION)
    }
    return { url: tab.url, title: tab.title }
  }

  async openUrl(url: string): Promise<void> {
    await browser.tabs.create({ url })
  }

  storage(): KeyValueStore {
    return {
      async get(key: string): Promise<string | null> {
        const found = await browser.storage.local.get(key)
        const value = found[key]
        return typeof value === 'string' ? value : null
      },
      async set(key: string, value: string): Promise<void> {
        await browser.storage.local.set({ [key]: value })
      },
    }
  }
}
