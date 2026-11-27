-- Dealer Fee Audit tables and unlock gate. NOT APPLIED. Review, then run in the
-- Supabase SQL editor only after Jacob approves launch. Safe to run more than once.
-- Requires public.unlocks from 20261127_loan_plan_audit.sql (already applied).
-- Does not change user_profiles, scenarios, loan_scenarios, record_loan_unlock,
-- or private.loan_unlock_gate.

create table if not exists public.dealer_fee_quotes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  name text not null default 'My quote',
  inputs jsonb not null default '{}'::jsonb,
  summary jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.dealer_fee_quotes is
  'Saved Dealer Fee Audit inputs for the signed-in user. Results are recomputed when a row is opened.';

create index if not exists dealer_fee_quotes_user_created_idx
  on public.dealer_fee_quotes (user_id, created_at desc);

alter table public.dealer_fee_quotes enable row level security;
alter table public.dealer_fee_quotes force row level security;

drop policy if exists "Users read own dealer fee quotes" on public.dealer_fee_quotes;
create policy "Users read own dealer fee quotes"
  on public.dealer_fee_quotes for select to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists "Users insert own dealer fee quotes" on public.dealer_fee_quotes;
create policy "Users insert own dealer fee quotes"
  on public.dealer_fee_quotes for insert to authenticated
  with check ((select auth.uid()) = user_id);

drop policy if exists "Users update own dealer fee quotes" on public.dealer_fee_quotes;
create policy "Users update own dealer fee quotes"
  on public.dealer_fee_quotes for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists "Users delete own dealer fee quotes" on public.dealer_fee_quotes;
create policy "Users delete own dealer fee quotes"
  on public.dealer_fee_quotes for delete to authenticated
  using ((select auth.uid()) = user_id);

revoke all on table public.dealer_fee_quotes from anon;
grant select, insert, update, delete on table public.dealer_fee_quotes to authenticated;

-- Unlock gate. Its own token (Streamlit secret DEALERFEE_UNLOCK_RECORD_TOKEN),
-- stored here only as a SHA-256 digest. After applying, set it once in the SQL
-- editor (never commit the real value):
--
--   insert into private.dealer_fee_unlock_gate (id, token_sha256)
--   values (1, encode(extensions.digest(convert_to('PASTE_DEALERFEE_UNLOCK_RECORD_TOKEN', 'utf8'), 'sha256'), 'hex'))
--   on conflict (id) do update set token_sha256 = excluded.token_sha256;
--
-- A missing row fails closed: record_dealer_fee_unlock will not write.

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table if not exists private.dealer_fee_unlock_gate (
  id integer primary key default 1,
  token_sha256 text not null,
  constraint dealer_fee_unlock_gate_singleton check (id = 1)
);

revoke all on table private.dealer_fee_unlock_gate from public, anon, authenticated;

create extension if not exists pgcrypto with schema extensions;

create or replace function public.record_dealer_fee_unlock(p_session_id text, p_token text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller uuid;
  expected text;
  presented text;
begin
  caller := auth.uid();
  if caller is null then
    raise exception 'login required' using errcode = '28000';
  end if;

  if p_session_id is null or p_session_id !~ '^cs_[A-Za-z0-9_]+$' or char_length(p_session_id) < 8 then
    raise exception 'invalid session' using errcode = '22023';
  end if;
  if p_token is null or char_length(p_token) < 16 then
    raise exception 'not allowed' using errcode = '42501';
  end if;

  select token_sha256 into expected from private.dealer_fee_unlock_gate where id = 1;

  presented := encode(extensions.digest(convert_to(p_token, 'utf8'), 'sha256'), 'hex');
  if expected is null or presented is distinct from expected then
    raise exception 'not allowed' using errcode = '42501';
  end if;

  -- One Checkout Session cannot unlock a second account (or a second product).
  if exists (
    select 1 from public.unlocks
    where stripe_checkout_session_id = p_session_id
      and (user_id is distinct from caller or product <> 'dealer_fee_audit')
  ) then
    raise exception 'session already used' using errcode = '23505';
  end if;

  if exists (
    select 1 from public.unlocks where user_id = caller and product = 'dealer_fee_audit'
  ) then
    return;
  end if;

  insert into public.unlocks (
    user_id, product, stripe_checkout_session_id, paid_at, terms_accepted_at, amount_cents
  ) values (
    caller, 'dealer_fee_audit', p_session_id, now(), now(), 700
  );
end;
$$;

comment on function public.record_dealer_fee_unlock(text, text) is
  'Writes the signed-in user''s dealer_fee_audit unlock after the app has checked the Checkout Session with Stripe. The token must match private.dealer_fee_unlock_gate.';

revoke all on function public.record_dealer_fee_unlock(text, text) from public, anon;
grant execute on function public.record_dealer_fee_unlock(text, text) to authenticated;

create or replace function public.delete_my_dealer_fee_unlock()
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.uid() is null then
    raise exception 'login required' using errcode = '28000';
  end if;
  delete from public.unlocks where user_id = auth.uid() and product = 'dealer_fee_audit';
end;
$$;

comment on function public.delete_my_dealer_fee_unlock() is
  'Deletes only the caller''s dealer_fee_audit unlock row. It cannot insert one.';

revoke all on function public.delete_my_dealer_fee_unlock() from public, anon;
grant execute on function public.delete_my_dealer_fee_unlock() to authenticated;
