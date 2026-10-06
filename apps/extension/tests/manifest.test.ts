import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

interface Manifest {
  manifest_version: number
  permissions: string[]
  host_permissions?: string[]
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
})
