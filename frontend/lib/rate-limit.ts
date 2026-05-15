// Tiny in-memory rate limiter. Per-process, so this protects against single
// burst sources but NOT against distributed attacks across Vercel instances.
// Good enough for an MVP / personal-scale broker.
//
// Upgrade path when you need real protection:
//   - @upstash/ratelimit + an Upstash Redis instance (free tier covers it)
//   - Vercel KV (same thing under different branding)
//   - Cloudflare Rate Limiting Rules in front of the deployment
// Swapping is a 10-line change in the routes that call rateLimit().

interface Bucket {
  count: number
  resetAt: number
}

const buckets = new Map<string, Bucket>()

/** Returns true if the request is allowed, false if it should be rejected. */
export function rateLimit(key: string, max: number, windowMs: number): boolean {
  const now = Date.now()
  const entry = buckets.get(key)
  if (!entry || entry.resetAt < now) {
    buckets.set(key, { count: 1, resetAt: now + windowMs })
    return true
  }
  if (entry.count >= max) return false
  entry.count++
  return true
}

/** Best-effort cleanup so the map doesn't grow forever. */
export function rateLimitGc(): void {
  const now = Date.now()
  for (const [k, v] of buckets) {
    if (v.resetAt < now) buckets.delete(k)
  }
}

/** Pull the client IP from common proxy headers. */
export function clientIp(request: Request): string {
  const xff = request.headers.get('x-forwarded-for')
  if (xff) return xff.split(',')[0].trim()
  return request.headers.get('x-real-ip') ?? 'unknown'
}
