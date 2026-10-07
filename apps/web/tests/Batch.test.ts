// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/svelte'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { PRESETS, baseIntent, findPreset } from '../src/lib/presets'
import Batch from '../src/screens/Batch.svelte'
import { api } from '../src/lib/api'

vi.mock('../src/lib/api', () => ({
  api: { createBatch: vi.fn() },
}))

const createBatch = vi.mocked(api.createBatch)

afterEach(() => {
  cleanup()
})

beforeEach(() => {
  createBatch.mockReset()
})

async function paste(...lines: string[]): Promise<void> {
  const area = screen.getByPlaceholderText(/one URL per line/)
  await fireEvent.input(area, { target: { value: lines.join('\n') } })
}

describe('Batch screen', () => {
  it('renders every preset and queues the selected conversion intent', async () => {
    render(Batch, { props: {} })
    const select = screen.getByRole('combobox', { name: 'Output preset' })
    expect(Array.from(select.querySelectorAll('option'), (option) => option.value)).toEqual(
      PRESETS.map((preset) => preset.id),
    )
    await fireEvent.change(select, { target: { value: 'sticker' } })
    expect(screen.getByText(/Import into WhatsApp is not guaranteed/)).toBeTruthy()
    createBatch.mockResolvedValue({ results: [] })
    await paste('https://example.com/1')
    await fireEvent.click(screen.getByText('Queue 1 URL'))
    expect(createBatch).toHaveBeenCalledWith({
      items: [{ url: 'https://example.com/1', intent: findPreset('sticker').intent, priority: 0 }],
    })
  })

  it('counts pasted urls on the queue button', async () => {
    render(Batch, { props: {} })
    expect(screen.getByText('Queue 0 URLs')).toBeTruthy()
    await paste('https://example.com/1', '', '  https://example.com/2  ')
    expect(screen.getByText('Queue 2 URLs')).toBeTruthy()
  })

  it('uses the singular when there is exactly one url', async () => {
    render(Batch, { props: {} })
    await paste('https://example.com/1')
    expect(screen.getByText('Queue 1 URL')).toBeTruthy()
  })

  it('refuses to submit without urls', async () => {
    render(Batch, { props: {} })
    await fireEvent.click(screen.getByText('Queue 0 URLs'))
    expect(screen.getByText('Paste at least one URL, one per line.')).toBeTruthy()
    expect(createBatch).not.toHaveBeenCalled()
  })

  it('refuses batches over the backend limit of 100', async () => {
    render(Batch, { props: {} })
    await paste(...Array.from({ length: 101 }, (_, i) => `https://example.com/${i}`))
    await fireEvent.click(screen.getByText('Queue 101 URLs'))
    expect(screen.getByText('At most 100 URLs per batch.')).toBeTruthy()
    expect(createBatch).not.toHaveBeenCalled()
  })

  it('submits every url with the selected preset and default priority', async () => {
    render(Batch, { props: {} })
    createBatch.mockResolvedValue({
      results: [
        { index: 0, status: 'created', job: { id: 'a', state: 'QUEUED', title: 'V', priority: 0 } },
        { index: 1, status: 'created', job: { id: 'b', state: 'QUEUED', title: 'W', priority: 0 } },
      ],
    })
    await paste('https://example.com/1', 'https://example.com/2')
    await fireEvent.click(screen.getByText('Queue 2 URLs'))
    await screen.findByText('2 created · 0 duplicates · 0 errors')
    expect(createBatch).toHaveBeenCalledTimes(1)
    expect(createBatch).toHaveBeenCalledWith({
      items: [
        { url: 'https://example.com/1', intent: baseIntent(), priority: 0 },
        { url: 'https://example.com/2', intent: baseIntent(), priority: 0 },
      ],
    })
  })

  it('renders created, duplicate and error rows with a summary', async () => {
    const onopen = vi.fn()
    render(Batch, { props: { onopen } })
    createBatch.mockResolvedValue({
      results: [
        { index: 0, status: 'created', job: { id: 'a', state: 'QUEUED', title: 'V', priority: 0 } },
        {
          index: 1,
          status: 'duplicate',
          job: { id: 'b', state: 'QUEUED', title: null, priority: 0 },
        },
        { index: 2, status: 'error', error: { code: 'BAD', message: 'nope' } },
      ],
    })
    await paste('https://example.com/1', 'https://example.com/2', 'https://example.com/3')
    await fireEvent.click(screen.getByText('Queue 3 URLs'))
    await screen.findByText('1 created · 1 duplicates · 1 errors')
    expect(screen.getByText('queued')).toBeTruthy()
    expect(screen.getByText('already queued')).toBeTruthy()
    expect(screen.getByText('error', { selector: 'span' })).toBeTruthy()
    expect(screen.getByText('BAD: nope')).toBeTruthy()
    await fireEvent.click(screen.getByText('V'))
    expect(onopen).toHaveBeenCalledWith('a')
  })

  it('surfaces backend failures as plain messages', async () => {
    render(Batch, { props: {} })
    createBatch.mockRejectedValue(new Error('service down'))
    await paste('https://example.com/1')
    await fireEvent.click(screen.getByText('Queue 1 URL'))
    await screen.findByText('service down')
  })
})
