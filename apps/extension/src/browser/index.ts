import { ChromiumBridge } from './chrome'
import { FirefoxBridge } from './firefox'
import type { BrowserBridge } from './types'

declare const browser: typeof chrome | undefined

function detect(): BrowserBridge {
  return typeof browser === 'undefined' ? new ChromiumBridge() : new FirefoxBridge()
}

let bridge: BrowserBridge | undefined

export function getBridge(): BrowserBridge {
  bridge ??= detect()
  return bridge
}

export type { ActiveTab, BrowserBridge } from './types'
