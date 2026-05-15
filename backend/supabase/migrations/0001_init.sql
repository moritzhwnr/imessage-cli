-- Run this once in Supabase dashboard → SQL Editor.
-- Creates the two tables our API needs. Supabase Auth manages auth.users
-- automatically; we just FK to it.

create table public.api_keys (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  key_hash    text not null unique,
  created_at  timestamptz not null default now(),
  last_used_at timestamptz
);

-- Lookup-by-hash is the hot path on every authenticated request.
create index api_keys_key_hash_idx on public.api_keys(key_hash);
create index api_keys_user_id_idx on public.api_keys(user_id);

create table public.tunnels (
  user_id       uuid primary key references auth.users(id) on delete cascade,
  url           text not null,
  tunnel_token  text not null,  -- TODO: encrypt at rest before production
  updated_at    timestamptz not null default now()
);

-- RLS: lock both tables down by default. All access goes through the service
-- role key (which bypasses RLS), so no policies are needed for our routes.
-- The lock-down prevents direct PostgREST access leaking data if a key ever
-- escapes.
alter table public.api_keys enable row level security;
alter table public.tunnels  enable row level security;
