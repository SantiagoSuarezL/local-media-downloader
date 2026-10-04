export interface ActiveTab {
  url?: string
  title?: string
}

export interface BrowserBridge {
  readonly name: 'chromium' | 'firefox'
  getActiveTab(): Promise<ActiveTab>
  openUrl(url: string): Promise<void>
}
