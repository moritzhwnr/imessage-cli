// Password policy + breached-password check.
//
// Rules:
//   - Minimum 12 characters
//   - Reject passwords found in the HaveIBeenPwned breach corpus, checked
//     via the k-anonymity range API: only the first 5 chars of the SHA-1
//     hash leave our server, so we never expose the user's password.
//   - HIBP failures (network, timeout) fail OPEN — don't block signup if
//     the third party is down. Better UX than a hard dependency.

import { createHash } from 'node:crypto'

const MIN_LENGTH = 12

export type PasswordCheck = { ok: true } | { ok: false; error: string }

export async function validatePassword(password: string): Promise<PasswordCheck> {
  if (password.length < MIN_LENGTH) {
    return {
      ok: false,
      error: `password must be at least ${MIN_LENGTH} characters`,
    }
  }
  if (process.env.SKIP_PWNED_CHECK === '1') {
    return { ok: true }
  }

  try {
    // SHA-1 of the password, uppercase hex. Send only the first 5 chars to
    // HIBP; they return all suffixes matching that prefix. We compare locally.
    const sha1 = createHash('sha1').update(password).digest('hex').toUpperCase()
    const prefix = sha1.slice(0, 5)
    const suffix = sha1.slice(5)

    const resp = await fetch(
      `https://api.pwnedpasswords.com/range/${prefix}`,
      {
        signal: AbortSignal.timeout(3000),
        headers: { 'Add-Padding': 'true' }, // hides response size from network observers
      },
    )
    if (!resp.ok) return { ok: true } // fail open

    const text = await resp.text()
    const matched = text.split(/\r?\n/).some((line) => {
      const [hashSuffix] = line.split(':')
      return hashSuffix.trim() === suffix
    })
    if (matched) {
      return {
        ok: false,
        error:
          'this password has appeared in a known data breach. choose a different one.',
      }
    }
  } catch {
    // Timeout / DNS / etc — fail open. Don't make signup depend on a 3rd party.
  }
  return { ok: true }
}
