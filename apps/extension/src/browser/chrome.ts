import type { ActiveTab, BrowserBridge, KeyValueStore } from './types'

const ERROR_NO_ACTIVE_TAB = 'No active tab available'
const ERROR_TABS_PERMISSION = 'The activeTab permission was not granted'

export class ChromiumBridge implements BrowserBridge {
  readonly name = 'chromium' as const

  async getActiveTab(): Promise<ActiveTab> {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
    if (!tab) {
      throw new Error(ERROR_NO_ACTIVE_TAB)
    }
    if (tab.url === undefined) {
      throw new Error(ERROR_TABS_PERMISSION)
    }
    return { url: tab.url, title: tab.title }
  }

  async openUrl(url: string): Promise<void> {
    await chrome.tabs.create({ url })
  }

  storage(): KeyValueStore {
    return {
      async get(key: string): Promise<string | null> {
        const found = await chrome.storage.local.get(key)
        const value = found[key]
        return typeof value === 'string' ? value : null
      },
      async set(key: string, value: string): Promise<void> {
        await chrome.storage.local.set({ [key]: value })
      },
    }
  }
}
