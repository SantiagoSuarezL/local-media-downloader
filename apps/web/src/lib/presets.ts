import type { OutputIntent } from '@lmd/contracts'

export interface Preset {
  id: string
  label: string
  intent: OutputIntent
}

export function baseIntent(overrides: Partial<OutputIntent> = {}): OutputIntent {
  return {
    media: 'video',
    quality: 'best',
    container: 'mp4',
    audio: 'include',
    video_codec: 'source',
    processing: { resize: null, trim: null },
    ...overrides,
  }
}

export const PRESETS: Preset[] = [
  { id: 'best', label: 'Best available', intent: baseIntent() },
  { id: 'video', label: 'Video', intent: baseIntent() },
  {
    id: 'audio',
    label: 'Audio (M4A)',
    intent: baseIntent({ media: 'audio', container: 'm4a', audio: 'only' }),
  },
  { id: 'mp4', label: 'MP4', intent: baseIntent({ container: 'mp4' }) },
  {
    id: 'mp3',
    label: 'MP3',
    intent: baseIntent({ media: 'audio', container: 'mp3', audio: 'only' }),
  },
  {
    id: 'video-only',
    label: 'Video only',
    intent: baseIntent({ container: 'mp4', audio: 'remove' }),
  },
  {
    id: 'no-audio',
    label: 'No audio',
    intent: baseIntent({ container: 'mp4', audio: 'remove' }),
  },
  { id: 'webm', label: 'WebM', intent: baseIntent({ container: 'webm' }) },
  { id: 'gif', label: 'GIF', intent: baseIntent({ container: 'gif', audio: 'remove' }) },
  {
    id: 'webp',
    label: 'Animated WebP',
    intent: baseIntent({ container: 'webp', audio: 'remove' }),
  },
  { id: 'mobile', label: 'Mobile (MP4, up to 720p)', intent: baseIntent({ container: 'mobile' }) },
  {
    id: 'sticker',
    label: 'WhatsApp sticker (WebP)',
    intent: baseIntent({ container: 'sticker', audio: 'remove' }),
  },
  {
    id: 'mkv',
    label: 'MKV',
    intent: baseIntent({ container: 'mkv' }),
  },
  {
    id: 'm4a',
    label: 'M4A (audio only)',
    intent: baseIntent({ media: 'audio', container: 'm4a', audio: 'only' }),
  },
]

export function findPreset(id: string): Preset {
  return PRESETS.find((p) => p.id === id) ?? PRESETS[0]
}
