// POST /api/tunnels/register
//   header:  Authorization: Bearer <api_key>
//   body:    { url, tunnel_token }
//
// The CLI calls this every time it starts `serve --public`. We upsert by
// user_id so a single user has at most one active tunnel.
//
// IMPORTANT design note — why tunnel_token lives here:
//   The local CLI server has its own bearer auth (different from the user's
//   API key). When the broker proxies an MCP request, it must present THAT
//   token upstream so cloudflared → local server passes auth. We store the
//   tunnel_token alongside the URL and use it in the proxy route.
//   This token IS plaintext in the DB. For an MVP this is acceptable but
//   should be migrated to encrypted-at-rest (pgsodium, Supabase Vault, or
//   column-level encryption) before this is anything close to production.

import { NextResponse } from 'next/server'
import { authenticateApiKey } from '@/lib/auth'
import { encryptToken } from '@/lib/crypto'
import { clientIp, rateLimit } from '@/lib/rate-limit'
import { getSupabaseAdmin } from '@/lib/supabase-admin'

// SSRF guard: only allow tunnels registered with hostnames we trust to be
// actual reverse tunnels (not internal services or arbitrary URLs). A
// permissive policy here would turn the broker into an open proxy able to
// reach internal networks, cloud metadata endpoints, etc.
//
// Override via env: ALLOWED_TUNNEL_HOST_SUFFIXES="trycloudflare.com,tunnels.example.com"
const ALLOWED_TUNNEL_HOST_SUFFIXES = (
  process.env.ALLOWED_TUNNEL_HOST_SUFFIXES ?? 'trycloudflare.com'
)
  .split(',')
  .map((s) => s.trim().toLowerCase())
  .filter(Boolean)

function isAllowedTunnelHost(host: string): boolean {
  const h = host.toLowerCase()
  return ALLOWED_TUNNEL_HOST_SUFFIXES.some(
    (suffix) => h === suffix || h.endsWith('.' + suffix),
  )
}

export async function POST(request: Request) {
  // Authenticate first so the rate-limit key is per-user where possible.
  const auth = await authenticateApiKey(request)
  if (!auth.ok) {
    // Unauth requests rate-limited by IP to slow down api-key guessing.
    if (!rateLimit(`register:ip:${clientIp(request)}`, 20, 60_000)) {
      return NextResponse.json({ error: 'too many requests' }, { status: 429 })
    }
    return NextResponse.json({ error: auth.error }, { status: auth.status })
  }
  // Per-user limit: 60/min is generous (CLI re-registers on every restart
  // and reconnect), but still throttles a misbehaving client.
  if (!rateLimit(`register:user:${auth.userId}`, 60, 60_000)) {
    return NextResponse.json({ error: 'too many requests' }, { status: 429 })
  }

  let body: { url?: string; tunnel_token?: string }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: 'invalid JSON body' }, { status: 400 })
  }

  const { url, tunnel_token } = body
  if (!url || !tunnel_token) {
    return NextResponse.json(
      { error: 'url and tunnel_token are required' },
      { status: 400 },
    )
  }

  // Validate the URL: HTTPS only AND hostname must match the allowlist.
  // Without the hostname check, an authenticated user could register
  // https://internal-corp-system.example.com and use the broker as a proxy
  // to reach private networks / cloud metadata / etc.
  let parsed: URL
  try {
    parsed = new URL(url)
  } catch {
    return NextResponse.json({ error: 'url is not a valid URL' }, { status: 400 })
  }
  if (parsed.protocol !== 'https:') {
    return NextResponse.json({ error: 'url must be https' }, { status: 400 })
  }
  if (!isAllowedTunnelHost(parsed.hostname)) {
    return NextResponse.json(
      {
        error: `tunnel host not allowed (must be one of: *.${ALLOWED_TUNNEL_HOST_SUFFIXES.join(', *.')})`,
      },
      { status: 400 },
    )
  }

  const admin = getSupabaseAdmin()
  const { error } = await admin.from('tunnels').upsert({
    user_id: auth.userId,
    url,
    // Encrypt at rest — the DB now holds opaque ciphertext. A DB leak (or
    // a curious team-member with Supabase access) no longer hands the
    // attacker working credentials for every user's local MCP server.
    tunnel_token: encryptToken(tunnel_token),
    updated_at: new Date().toISOString(),
  })
  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  return new NextResponse(null, { status: 204 })
}
