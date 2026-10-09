import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

interface Manifest {
  manifest_version: number
  permissions: string[]
  host_permissions?: string[]
  icons?: Record<string, string>
  action?: { default_icon?: Record<string, string> }
}

const manifest = JSON.parse(
  readFileSync(fileURLToPath(new URL('../src/manifest.json', import.meta.url)), 'utf8'),
) as Manifest

describe('extension manifest', () => {
  it('requests only the permissions the MVP needs', () => {
    expect(manifest.manifest_version).toBe(3)
    expect([...manifest.permissions].sort()).toEqual(['activeTab', 'storage'])
  })

  it('never asks for a host outside loopback', () => {
    // Least privilege is enforced here, not just documented: an extension that
    // can reach arbitrary hosts would hand the user's page URL to a remote
    // service the moment a URL is sent.
    expect(manifest.host_permissions).toEqual(['http://127.0.0.1/*', 'http://localhost/*'])
  })

  it('ships a toolbar icon in every declared size', () => {
    // Without icons the toolbar shows a bare "L": the extension looks
    // unfinished and is harder to pick out. Every declared path must exist in
    // public/ so Vite copies it into dist/ beside the manifest.
    const icons = manifest.icons ?? {}
    expect(Object.keys(icons).sort()).toEqual(['128', '16', '32', '48'])
    for (const [size, path] of Object.entries(icons)) {
      expect(path).toBe(`icons/icon-${size}.png`)
      expect(existsSync(fileURLToPath(new URL(`../public/${path}`, import.meta.url)))).toBe(true)
    }
    expect(manifest.action?.default_icon).toEqual(icons)
  })
})
