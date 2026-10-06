import { getBridge } from '../browser/index'
import {
  DEFAULT_SERVICE_URL,
  SERVICE_URL_KEY,
  buildDashboardUrl,
  normalizeServiceUrl,
  validateMediaUrl,
} from '../lib/handoff'
import { checkHealth, type ConnectionStatus } from '../service/client'

const el = <T extends HTMLElement>(id: string): T | null => document.getElementById(id) as T | null

const pageUrl = el<HTMLParagraphElement>('page-url')
const pageTitle = el<HTMLParagraphElement>('page-title')
const pageHint = el<HTMLParagraphElement>('page-hint')
const handoff = el<HTMLButtonElement>('handoff')
const manualUrl = el<HTMLInputElement>('manual-url')
const manualHandoff = el<HTMLButtonElement>('manual-handoff')
const health = el<HTMLSpanElement>('health')
const healthText = el<HTMLSpanElement>('health-text')
const serviceUrl = el<HTMLInputElement>('service-url')
const serviceSave = el<HTMLButtonElement>('service-save')
const serviceHint = el<HTMLParagraphElement>('service-hint')

const bridge = getBridge()
let service: string = DEFAULT_SERVICE_URL
let status: ConnectionStatus = 'offline'

function setHealth(next: ConnectionStatus, text: string): void {
  status = next
  if (health) {
    health.dataset.status = next
  }
  if (healthText) {
    healthText.textContent = text
  }
  refreshButtons()
}

function refreshButtons(): void {
  // The handoff button needs both a usable URL and a reachable service: opening
  // a tab to an offline service would land on the browser's error page.
  const pageOk = validateMediaUrl(pageUrl?.dataset.url).ok
  const manualOk = validateMediaUrl(manualUrl?.value).ok
  if (handoff) {
    handoff.disabled = !(pageOk && status === 'connected')
  }
  if (manualHandoff) {
    manualHandoff.disabled = !(manualOk && status === 'connected')
  }
}

async function probe(): Promise<void> {
  const result = await checkHealth(service)
  if (result.status === 'connected') {
    const version = result.version ? ` ${result.version}` : ''
    setHealth('connected', `Connected${version}`)
    return
  }
  setHealth('offline', 'Offline')
  if (pageHint && !pageHint.classList.contains('error')) {
    pageHint.textContent = result.detail
  }
}

async function openInService(rawUrl: string): Promise<void> {
  const validation = validateMediaUrl(rawUrl)
  if (!validation.ok) {
    if (pageHint) {
      pageHint.classList.add('error')
      pageHint.textContent = validation.reason ?? 'This URL cannot be sent.'
    }
    return
  }
  await bridge.openUrl(buildDashboardUrl(service, rawUrl.trim()))
  window.close()
}

async function loadServiceUrl(): Promise<void> {
  const stored = await bridge.storage().get(SERVICE_URL_KEY)
  service = normalizeServiceUrl(stored ?? '') ?? DEFAULT_SERVICE_URL
  if (serviceUrl) {
    serviceUrl.value = service
  }
}

async function saveServiceUrl(): Promise<void> {
  const requested = serviceUrl?.value ?? ''
  const normalized = normalizeServiceUrl(requested)
  if (normalized === null) {
    if (serviceHint) {
      serviceHint.classList.add('error')
      serviceHint.textContent =
        'Enter a loopback address such as http://127.0.0.1:8765 (nothing else is allowed).'
    }
    return
  }
  if (serviceHint) {
    serviceHint.classList.remove('error')
    serviceHint.textContent = `Service address set to ${normalized}.`
  }
  service = normalized
  await bridge.storage().set(SERVICE_URL_KEY, normalized)
  await probe()
}

async function main(): Promise<void> {
  await loadServiceUrl()
  await probe()

  try {
    const tab = await bridge.getActiveTab()
    if (pageTitle) {
      pageTitle.textContent = tab.title ?? ''
    }
    if (pageUrl) {
      pageUrl.dataset.url = tab.url ?? ''
      pageUrl.textContent = tab.url ?? 'This page has no URL.'
    }
    const validation = validateMediaUrl(tab.url)
    if (pageHint) {
      pageHint.classList.toggle('error', !validation.ok)
      pageHint.textContent = validation.ok
        ? 'Ready to send to the local service.'
        : (validation.reason ?? '')
    }
  } catch (error) {
    if (pageUrl) {
      pageUrl.textContent = 'This page URL is not available to the extension.'
    }
    if (pageHint) {
      pageHint.classList.add('error')
      pageHint.textContent = error instanceof Error ? error.message : String(error)
    }
  }

  refreshButtons()
}

handoff?.addEventListener('click', () => {
  void openInService(pageUrl?.dataset.url ?? '')
})
manualHandoff?.addEventListener('click', () => {
  void openInService(manualUrl?.value ?? '')
})
manualUrl?.addEventListener('input', refreshButtons)
serviceSave?.addEventListener('click', () => {
  void saveServiceUrl()
})
serviceUrl?.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    void saveServiceUrl()
  }
})

void main()
