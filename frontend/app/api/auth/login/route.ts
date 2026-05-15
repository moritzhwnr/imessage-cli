// POST /api/auth/login
//   body:    { email, password }
//   returns: { user_id, api_key }
//
// Verifies the password by calling Supabase's signInWithPassword, then issues
// a NEW API key. We don't return an existing key because we never store the
// plaintext — each login = a fresh key. Old keys stay valid until revoked
// (which we'll expose later via a /api/keys/{id} DELETE endpoint).

import { NextResponse } from 'next/server'
import { generateApiKey } from '@/lib/api-keys'
import { clientIp, rateLimit } from '@/lib/rate-limit'
import { getSupabaseAdmin } from '@/lib/supabase-admin'

export async function POST(request: Request) {
  // IP-level throttle: 20/minute (covers honest typos + slow brute force).
  if (!rateLimit(`login:ip:${clientIp(request)}`, 20, 60_000)) {
    return NextResponse.json(
      { error: 'too many login attempts; try again later' },
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

  // Per-email throttle (5/min) — even if an attacker rotates IPs, they
  // can't bang on a single account faster than this.
  if (!rateLimit(`login:email:${email.toLowerCase()}`, 5, 60_000)) {
    return NextResponse.json(
      { error: 'too many login attempts for this account; try again later' },
      { status: 429 },
    )
  }

  // GOTCHA: signInWithPassword mutates the client's auth state — after
  // this call, the client uses the USER's JWT (subject to RLS), not the
  // service_role key. So we use one client to verify the password and a
  // FRESH client (still service_role) for the privileged insert below.
  const authClient = getSupabaseAdmin()
  const { data, error } = await authClient.auth.signInWithPassword({ email, password })
  if (error || !data.user) {
    return NextResponse.json({ error: 'invalid credentials' }, { status: 401 })
  }

  const admin = getSupabaseAdmin() // fresh client → service_role context
  const { plaintext, hash } = generateApiKey()
  const { error: insertError } = await admin
    .from('api_keys')
    .insert({ user_id: data.user.id, key_hash: hash })
  if (insertError) {
    return NextResponse.json({ error: insertError.message }, { status: 500 })
  }

  return NextResponse.json({ user_id: data.user.id, api_key: plaintext })
}
