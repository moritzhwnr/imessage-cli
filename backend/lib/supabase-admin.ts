// Server-side Supabase client using the SERVICE ROLE key.
// This key bypasses RLS, so:
//   - NEVER ship this to a browser bundle.
//   - Only import from server-side code (route handlers, server components).
// We instantiate per-request (cheap) and disable session persistence —
// there are no user sessions to track here, every call is a one-shot.

import { createClient, SupabaseClient } from '@supabase/supabase-js'

export function getSupabaseAdmin(): SupabaseClient {
  const url = process.env.SUPABASE_URL
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY
  if (!url || !serviceKey) {
    throw new Error(
      'Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY env vars. ' +
        'Copy .env.local.example to .env.local and fill them in.',
    )
  }

  // Sanity-check the JWT's role claim. If someone pastes the anon key here
  // by mistake, RLS will silently block every insert and you'll spend an
  // hour debugging "row-level security policy" errors. Fail loudly instead.
  // Supabase JWTs are unsigned-payload-readable: base64url-decode the middle
  // segment. We're inspecting, not validating — the server still trusts the
  // key as-is, so no crypto needed here.
  try {
    const payload = JSON.parse(
      Buffer.from(serviceKey.split('.')[1], 'base64url').toString('utf8'),
    )
    if (payload.role !== 'service_role') {
      throw new Error(
        `SUPABASE_SERVICE_ROLE_KEY has role="${payload.role}", expected "service_role". ` +
          'You probably pasted the anon key by mistake. Check Supabase dashboard → Settings → API.',
      )
    }
  } catch (e) {
    if (e instanceof Error && e.message.includes('role=')) throw e
    // JWT parse failed — let createClient surface the real error.
  }

  return createClient(url, serviceKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  })
}
