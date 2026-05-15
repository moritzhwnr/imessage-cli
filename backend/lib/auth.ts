// Bearer token auth for protected routes.
//
// Reads `Authorization: Bearer <api_key>`, looks up the hash in the
// api_keys table, and returns the associated user_id (or an error tuple).
// The fire-and-forget `last_used_at` update gives us cheap activity tracking
// without blocking the request.

import { hashApiKey } from './api-keys'
import { getSupabaseAdmin } from './supabase-admin'

export type AuthResult =
  | { ok: true; userId: string }
  | { ok: false; status: number; error: string }

export async function authenticateApiKey(request: Request): Promise<AuthResult> {
  const auth = request.headers.get('authorization')
  if (!auth?.toLowerCase().startsWith('bearer ')) {
    return { ok: false, status: 401, error: 'missing Authorization: Bearer header' }
  }
  const token = auth.slice(7).trim()
  if (!token) {
    return { ok: false, status: 401, error: 'empty bearer token' }
  }

  const hash = hashApiKey(token)
  const admin = getSupabaseAdmin()
  const { data, error } = await admin
    .from('api_keys')
    .select('user_id')
    .eq('key_hash', hash)
    .maybeSingle()

  if (error || !data) {
    return { ok: false, status: 401, error: 'invalid api key' }
  }

  // Fire-and-forget — don't await, don't surface errors.
  void admin
    .from('api_keys')
    .update({ last_used_at: new Date().toISOString() })
    .eq('key_hash', hash)

  return { ok: true, userId: data.user_id }
}
