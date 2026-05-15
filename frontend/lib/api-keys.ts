// API key generation and hashing.
//
// Why SHA-256 (not argon2/bcrypt) for API keys:
//   - API keys are 256 bits of cryptographic randomness. Brute force is
//     infeasible regardless of hash speed.
//   - argon2/bcrypt are designed to slow down attacks on LOW-entropy
//     passwords. Wrong tool for high-entropy random keys, and slow hashes
//     would hurt request latency on every authenticated call.
//   - SHA-256 is fast, sufficient, and what Stripe / GitHub use for API keys.

import { createHash, randomBytes } from 'node:crypto'

export interface IssuedApiKey {
  plaintext: string // returned to the user ONCE, never stored
  hash: string // stored in DB; used to look up
}

export function generateApiKey(): IssuedApiKey {
  // 32 random bytes → 43-char base64url string (no padding, URL-safe).
  const plaintext = randomBytes(32).toString('base64url')
  const hash = hashApiKey(plaintext)
  return { plaintext, hash }
}

export function hashApiKey(plaintext: string): string {
  return createHash('sha256').update(plaintext).digest('hex')
}
