// AES-256-GCM encryption for tunnel tokens.
//
// Why GCM: it's an authenticated cipher, so decryption fails (throws) if the
// ciphertext was tampered with. No need to compose MAC ourselves.
//
// Storage format: base64( iv || tag || ciphertext )
//   - iv (12 bytes)  — random per encryption; NEVER reuse with the same key
//   - tag (16 bytes) — auth tag, GCM standard
//   - ciphertext     — variable length
// Concatenating into a single column keeps the schema simple.
//
// Key management: 32 random bytes, base64-encoded in env var.
// Generate one with:
//   node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"
// Rotate by re-encrypting all rows (out of scope for this MVP — a one-off
// migration script is the right shape when you eventually need it).

import { createCipheriv, createDecipheriv, randomBytes } from 'node:crypto'

const ALGO = 'aes-256-gcm'
const IV_LEN = 12 // GCM standard nonce size
const TAG_LEN = 16

function getKey(): Buffer {
  const raw = process.env.TUNNEL_TOKEN_ENCRYPTION_KEY
  if (!raw) {
    throw new Error(
      'Missing TUNNEL_TOKEN_ENCRYPTION_KEY env var. Generate one with: ' +
        `node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"`,
    )
  }
  const buf = Buffer.from(raw, 'base64')
  if (buf.length !== 32) {
    throw new Error(
      `TUNNEL_TOKEN_ENCRYPTION_KEY must decode to 32 bytes, got ${buf.length}`,
    )
  }
  return buf
}

export function encryptToken(plaintext: string): string {
  const iv = randomBytes(IV_LEN)
  const cipher = createCipheriv(ALGO, getKey(), iv)
  const ciphertext = Buffer.concat([
    cipher.update(plaintext, 'utf8'),
    cipher.final(),
  ])
  const tag = cipher.getAuthTag()
  return Buffer.concat([iv, tag, ciphertext]).toString('base64')
}

export function decryptToken(stored: string): string {
  const buf = Buffer.from(stored, 'base64')
  if (buf.length < IV_LEN + TAG_LEN + 1) {
    throw new Error('encrypted blob too short')
  }
  const iv = buf.subarray(0, IV_LEN)
  const tag = buf.subarray(IV_LEN, IV_LEN + TAG_LEN)
  const ciphertext = buf.subarray(IV_LEN + TAG_LEN)
  const decipher = createDecipheriv(ALGO, getKey(), iv)
  decipher.setAuthTag(tag)
  const plaintext = Buffer.concat([
    decipher.update(ciphertext),
    decipher.final(),
  ])
  return plaintext.toString('utf8')
}
