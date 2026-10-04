import { getBridge } from '../browser/index'

const status = document.getElementById('status')

async function render(): Promise<void> {
  if (!status) {
    return
  }
  try {
    const tab = await getBridge().getActiveTab()
    status.textContent = tab.title ? `${tab.title} — ${tab.url ?? ''}` : (tab.url ?? '')
  } catch (error) {
    status.textContent = error instanceof Error ? error.message : String(error)
  }
}

void render()
