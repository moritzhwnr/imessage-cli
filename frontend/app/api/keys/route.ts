// GET /api/keys
//   header:  Authorization: Bearer <api_key>
//   returns: [{ id, created_at, last_used_at, current }]
//
// Lets a user audit which keys exist on their account. We hash plaintext
// at issue time so there's nothing identifying to show beyond timestamps
// and id. `current: true` marks the key used to make this very request,
// so the CLI can highlight "don't revoke me, I'm in use."

import { NextResponse } from 'next/server'
import { hashApiKey } from '@/lib/api-keys'
import { authenticateApiKey } from '@/lib/auth'
import { getSupabaseAdmin } from '@/lib/supabase-admin'

export async function GET(request: Request) {
  const auth = await authenticateApiKey(request)
  if (!auth.ok) {
    return NextResponse.json({ error: auth.error }, { status: auth.status })
  }

  // We need the bearer to flag the "current" key.
  const bearer = request.headers.get('authorization')!.slice(7).trim()
  const currentHash = hashApiKey(bearer)

  const admin = getSupabaseAdmin()
  const { data, error } = await admin
    .from('api_keys')
    .select('id, key_hash, created_at, last_used_at')
    .eq('user_id', auth.userId)
    .order('created_at', { ascending: false })

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  return NextResponse.json(
    data.map((k) => ({
      id: k.id,
      created_at: k.created_at,
      last_used_at: k.last_used_at,
      current: k.key_hash === currentHash,
    })),
  )
}
