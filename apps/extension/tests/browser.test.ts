import { describe, expect, it } from 'vitest'
import { ChromiumBridge } from '../src/browser/chrome'
import { FirefoxBridge } from '../src/browser/firefox'

const TAB = { id: 1, url: 'https://example.com/watch?v=1', title: 'Example' }

function stubChromeTabs(queryResult: unknown[]) {
  ;(globalThis as { chrome?: unknown }).chrome = {
    tabs: {
      query: async () => queryResult,
      create: async () => undefined,
    },
  }
}

function stubBrowserTabs(queryResult: unknown[]) {
  ;(globalThis as { browser?: unknown }).browser = {
    tabs: {
      query: async () => queryResult,
      create: async () => undefined,
    },
  }
}

describe('ChromiumBridge', () => {
  it('returns the active tab url', async () => {
    stubChromeTabs([TAB])
    const bridge = new ChromiumBridge()
    await expect(bridge.getActiveTab()).resolves.toEqual({
      url: TAB.url,
      title: TAB.title,
    })
  })

  it('fails explicitly when there is no active tab', async () => {
    stubChromeTabs([])
    await expect(new ChromiumBridge().getActiveTab()).rejects.toThrow('No active tab available')
  })
})

describe('FirefoxBridge', () => {
  it('returns the active tab url', async () => {
    stubBrowserTabs([TAB])
    const bridge = new FirefoxBridge()
    await expect(bridge.getActiveTab()).resolves.toEqual({
      url: TAB.url,
      title: TAB.title,
    })
  })

  it('fails explicitly when the url is not readable', async () => {
    stubBrowserTabs([{ id: 1, title: 'Example' }])
    await expect(new FirefoxBridge().getActiveTab()).rejects.toThrow(
      'The activeTab permission was not granted',
    )
  })
})
