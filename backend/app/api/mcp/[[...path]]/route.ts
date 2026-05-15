// ANY  /api/u/{userId}/mcp/{...path}
//
// The reverse proxy. MCP clients (Claude Desktop, etc.) point at
//   https://app.example.com/api/u/<their-user-id>/mcp
// with Authorization: Bearer <api_key>. We:
//   1. Validate the API key — and check it belongs to {userId}.
//   2. Look up that user's registered tunnel URL + tunnel_token.
//   3. Forward the request upstream, swapping the user's API key for the
//      tunnel's bearer token in the Authorization header.
//   4. Stream the response back as-is (MCP streamable HTTP returns SSE,
//      which means the response body is a long-lived stream).
//
// Why we hand the upstream Response.body straight to the client:
//   Next.js Route Handlers accept a ReadableStream as the body of a new
//   Response — Node-fetch's response body IS a ReadableStream, so this is a
//   zero-copy proxy that preserves SSE / chunked transfer encoding.

import { NextResponse } from 'next/server'
import { authenticateApiKey } from '@/lib/auth'
import { decryptToken } from '@/lib/crypto'
import { getSupabaseAdmin } from '@/lib/supabase-admin'

// Force Node runtime — the Edge runtime doesn't support streaming request
// bodies via `duplex: 'half'`, and we proxy whatever the MCP client sends.
export const runtime = 'nodejs'
// Disable caching — every proxied request must hit upstream.
export const dynamic = 'force-dynamic'

async function handler(
  request: Request,
  // Optional catch-all: `path` is undefined for /api/mcp itself, an array
  // like ["foo","bar"] for /api/mcp/foo/bar.
  context: { params: Promise<{ path?: string[] }> },
) {
  const { path } = await context.params
  const pathSegments = path ?? []

  // The API key alone identifies the user — no userId needed in the URL.
  // This makes the URL stable + clean (one per service, not per user),
  // which is the shape Poke / Claude Desktop / Cursor integrations expect:
  // a single URL plus a per-user bearer token in headers.
  const auth = await authenticateApiKey(request)
  if (!auth.ok) {
    return NextResponse.json({ error: auth.error }, { status: auth.status })
  }

  const admin = getSupabaseAdmin()
  const { data, error } = await admin
    .from('tunnels')
    .select('url, tunnel_token')
    .eq('user_id', auth.userId)
    .maybeSingle()
  if (error || !data) {
    return NextResponse.json(
      { error: 'no active tunnel registered for this user' },
      { status: 502 },
    )
  }

  // Build the upstream URL: <tunnel_url>/mcp/<subpath>?<query>
  // The local CLI server mounts MCP at /mcp, so we keep that prefix.
  const base = data.url.replace(/\/+$/, '')
  const subpath = pathSegments.length ? '/' + pathSegments.join('/') : ''
  const search = new URL(request.url).search
  const target = `${base}/mcp${subpath}${search}`

  // Decrypt the stored tunnel token. Failure here means either a stale row
  // from before encryption was enabled, or a key-rotation mishap — surface
  // as 502 since the broker can't reach the upstream without it.
  let tunnelToken: string
  try {
    tunnelToken = decryptToken(data.tunnel_token)
  } catch {
    return NextResponse.json(
      {
        error:
          'tunnel token unreadable; ask the user to restart `imessage-mcp serve --public`',
      },
      { status: 502 },
    )
  }

  // Clone request headers, swap Authorization, drop hop-by-hop / unsafe ones.
  const upstreamHeaders = new Headers(request.headers)
  upstreamHeaders.set('authorization', `Bearer ${tunnelToken}`)
  upstreamHeaders.delete('host')
  upstreamHeaders.delete('content-length') // fetch will recompute
  upstreamHeaders.delete('connection')

  const init: RequestInit & { duplex?: 'half' } = {
    method: request.method,
    headers: upstreamHeaders,
  }
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    init.body = request.body
    // Required by Node's fetch when streaming a request body. Without it,
    // Node will refuse to send the request and throw "RequestInit: duplex".
    init.duplex = 'half'
  }

  let upstream: Response
  try {
    upstream = await fetch(target, init)
  } catch (e) {
    return NextResponse.json(
      { error: `upstream fetch failed: ${(e as Error).message}` },
      { status: 502 },
    )
  }

  // Forward status + headers + streamed body. Drop transfer-encoding so
  // fetch can re-chunk; let Next set content-length when known.
  const respHeaders = new Headers(upstream.headers)
  respHeaders.delete('transfer-encoding')
  respHeaders.delete('connection')

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: respHeaders,
  })
}

export const GET = handler
export const POST = handler
export const DELETE = handler
export const PUT = handler
export const PATCH = handler
