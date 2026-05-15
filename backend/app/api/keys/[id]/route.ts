// DELETE /api/keys/[id]
//   header:  Authorization: Bearer <api_key>
//   returns: 204 on success
//
// Revokes one of the caller's API keys. user_id check prevents Alice from
// deleting Bob's keys even if she somehow learned a UUID.
//
// Revoking the SAME key used to call this endpoint is allowed (and useful —
// "rotate" works as new-key + revoke-old). The current request still
// succeeds because the key existed when auth ran; subsequent calls 401.

import { NextResponse } from 'next/server'
import { authenticateApiKey } from '@/lib/auth'
import { getSupabaseAdmin } from '@/lib/supabase-admin'

export async function DELETE(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  const auth = await authenticateApiKey(request)
  if (!auth.ok) {
    return NextResponse.json({ error: auth.error }, { status: auth.status })
  }

  const { id } = await context.params
  const admin = getSupabaseAdmin()
  // Two-column WHERE = the key must belong to the caller.
  const { error, count } = await admin
    .from('api_keys')
    .delete({ count: 'exact' })
    .eq('id', id)
    .eq('user_id', auth.userId)

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }
  if (count === 0) {
    // Either the id doesn't exist or it belongs to someone else. Don't
    // distinguish — gives nothing useful to an attacker probing IDs.
    return NextResponse.json({ error: 'not found' }, { status: 404 })
  }

  return new NextResponse(null, { status: 204 })
}
