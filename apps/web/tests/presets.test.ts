import { describe, expect, it } from 'vitest'
import { PRESETS, baseIntent, findPreset } from '../src/lib/presets'

describe('PRESETS', () => {
  it('has unique ids', () => {
    const ids = PRESETS.map((preset) => preset.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('keeps the default preset first (the UI selects it on load)', () => {
    expect(PRESETS[0].id).toBe('best')
  })

  it('gives every intent the keys the backend planner requires', () => {
    for (const preset of PRESETS) {
      expect(Object.keys(preset.intent).sort()).toEqual(
        ['audio', 'container', 'media', 'processing', 'quality', 'video_codec'].sort(),
      )
      expect(Object.keys(preset.intent.processing).sort()).toEqual(['crop', 'resize', 'trim'])
    }
  })

  it('only uses values the backend intent parser accepts', () => {
    for (const preset of PRESETS) {
      expect(['video', 'audio']).toContain(preset.intent.media)
      expect(['best', 'worst']).toContain(preset.intent.quality)
      expect(['include', 'remove', 'only']).toContain(preset.intent.audio)
      expect(preset.intent.video_codec).toBe('source')
    }
  })

  it('keeps audio-only presets consistent (media=audio requires audio=only)', () => {
    for (const preset of PRESETS) {
      if (preset.intent.media === 'audio') {
        expect(preset.intent.audio).toBe('only')
      }
      if (preset.intent.audio === 'only') {
        expect(preset.intent.media).toBe('audio')
      }
    }
  })

  it('exposes every phase 13 preset with a supported output target', () => {
    const expected: Record<string, [string, string, string]> = {
      video: ['video', 'mp4', 'include'],
      audio: ['audio', 'm4a', 'only'],
      mp3: ['audio', 'mp3', 'only'],
      mp4: ['video', 'mp4', 'include'],
      webm: ['video', 'webm', 'include'],
      gif: ['video', 'gif', 'remove'],
      webp: ['video', 'webp', 'remove'],
      'no-audio': ['video', 'mp4', 'remove'],
      mobile: ['video', 'mobile', 'include'],
      sticker: ['video', 'sticker', 'remove'],
    }
    for (const [id, [media, container, audio]] of Object.entries(expected)) {
      expect(findPreset(id).id).toBe(id)
      expect(findPreset(id).intent).toMatchObject({ media, container, audio })
    }
  })

  it('keeps the mp3 preset honest about what it produces', () => {
    const mp3 = findPreset('mp3')
    expect(mp3.intent.media).toBe('audio')
    expect(mp3.intent.container).toBe('mp3')
    expect(mp3.intent.audio).toBe('only')
  })
})

describe('findPreset', () => {
  it('resolves a known id', () => {
    expect(findPreset('webm').label).toBe('WebM')
  })

  it('falls back to the default instead of throwing on unknown ids', () => {
    expect(findPreset('does-not-exist')).toBe(PRESETS[0])
  })
})

describe('baseIntent', () => {
  it('builds a valid best-quality video intent by default', () => {
    expect(baseIntent()).toEqual({
      media: 'video',
      quality: 'best',
      container: 'mp4',
      audio: 'include',
      video_codec: 'source',
      processing: { resize: null, trim: null, crop: null },
    })
  })

  it('applies overrides without touching the other keys', () => {
    const intent = baseIntent({ media: 'audio', container: 'm4a', audio: 'only' })
    expect(intent.media).toBe('audio')
    expect(intent.quality).toBe('best')
    expect(intent.processing).toEqual({ resize: null, trim: null, crop: null })
  })
})
