export interface ActiveTab {
  url?: string
  title?: string
}

/** Minimal persistence surface: one string key, so tests can stub it. */
export interface KeyValueStore {
  get(key: string): Promise<string | null>
  set(key: string, value: string): Promise<void>
}

export interface BrowserBridge {
  readonly name: 'chromium' | 'firefox'
  getActiveTab(): Promise<ActiveTab>
  openUrl(url: string): Promise<void>
  /** Local extension storage (chrome.storage.local / browser.storage.local). */
  storage(): KeyValueStore
}
