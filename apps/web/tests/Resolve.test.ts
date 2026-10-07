// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/svelte'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../src/lib/api'
import { PRESETS, findPreset } from '../src/lib/presets'
import Resolve from '../src/screens/Resolve.svelte'

vi.mock('../src/lib/api', () => ({
  api: { resolve: vi.fn(), createJob: vi.fn() },
}))

afterEach(() => {
  cleanup()
  vi.resetAllMocks()
})

describe('Resolve presets', () => {
  it('renders all presets and submits the selected conversion intent', async () => {
    vi.mocked(api.resolve).mockResolvedValue({
      source: {
        url: 'https://example.com/v',
        title: 'Video',
        extractor: 'generic',
        uploader: null,
      },
      id: 'v',
      duration_seconds: 3,
      thumbnail_url: null,
      is_live: false,
      formats: [],
      warnings: [],
    })
    vi.mocked(api.createJob).mockResolvedValue({ id: 'job-1' } as Awaited<
      ReturnType<typeof api.createJob>
    >)
    render(Resolve, { props: {} })
    await fireEvent.input(screen.getByPlaceholderText('https://...'), {
      target: { value: 'https://example.com/v' },
    })
    await fireEvent.click(screen.getByText('Resolve', { selector: 'button' }))
    await screen.findByText('Video', { selector: 'h2' })
    const select = screen.getByRole('combobox', { name: 'Output preset' })
    expect(Array.from(select.querySelectorAll('option'), (option) => option.value)).toEqual(
      PRESETS.map((preset) => preset.id),
    )
    await fireEvent.change(select, { target: { value: 'sticker' } })
    expect(screen.getByText(/Import into WhatsApp is not guaranteed/)).toBeTruthy()
    await fireEvent.click(screen.getByText('Start: WhatsApp sticker (WebP)'))
    expect(api.createJob).toHaveBeenCalledWith({
      url: 'https://example.com/v',
      intent: findPreset('sticker').intent,
      title: 'Video',
    })
  })
})
