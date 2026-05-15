// POST /api/auth/signup
//   body:    { email, password }
//   returns: { user_id, api_key }
//
// Creates a Supabase auth user (email pre-confirmed so the CLI doesn't have
// to wait for a verification click), then issues a fresh API key and stores
// only its hash. The plaintext is returned to the caller ONCE — they save it
// to ~/.config/imessage-mcp/api_key.

import { NextResponse } from 'next/server'
import { generateApiKey } from '@/lib/api-keys'
import { validatePassword } from '@/lib/password'
import { clientIp, rateLimit } from '@/lib/rate-limit'
import { getSupabaseAdmin } from '@/lib/supabase-admin'

export async function POST(request: Request) {
  // 5 signups/hour/IP is harsh enough to make abuse uneconomic but won't
  // bother a real user who fat-fingers their password a few times.
  if (!rateLimit(`signup:${clientIp(request)}`, 5, 60 * 60_000)) {
    return NextResponse.json(
      { error: 'too many signup attempts; try again later' },
      { status: 429 },
    )
  }

  let body: { email?: string; password?: string }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: 'invalid JSON body' }, { status: 400 })
  }

  const { email, password } = body
  if (!email || !password) {
    return NextResponse.json(
      { error: 'email and password are required' },
      { status: 400 },
    )
  }
  const check = await validatePassword(password)
  if (!check.ok) {
    return NextResponse.json({ error: check.error }, { status: 400 })
  }

  const admin = getSupabaseAdmin()

  // email_confirm: true skips the verification email — fine for MVP. Re-enable
  // verification later by setting this to false AND adding a /api/auth/verify
  // endpoint that consumes the token from the Supabase email link.
  const { data, error } = await admin.auth.admin.createUser({
    email,
    password,
    email_confirm: true,
  })
  if (error || !data.user) {
    return NextResponse.json(
      { error: error?.message ?? 'signup failed' },
      // 409 if duplicate, 400 otherwise — Supabase's message contains the word
      // "registered" when it's a duplicate. Crude but works.
      { status: error?.message?.toLowerCase().includes('registered') ? 409 : 400 },
    )
  }

  const { plaintext, hash } = generateApiKey()
  const { error: insertError } = await admin
    .from('api_keys')
    .insert({ user_id: data.user.id, key_hash: hash })
  if (insertError) {
    return NextResponse.json({ error: insertError.message }, { status: 500 })
  }

  return NextResponse.json({ user_id: data.user.id, api_key: plaintext })
}
