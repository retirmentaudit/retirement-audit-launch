-- Close the Loan Plan Audit unlock write gap.
-- Run this in the Supabase SQL editor. It is safe to run more than once.
-- Do not edit 20261127_loan_plan_audit.sql; that file is already applied.
-- This file does not change public.user_profiles, public.scenarios, or public.loan_scenarios.
-- Retirement Audit is unchanged.

-- Signed-in users may read their own unlock row. They may not insert, update, or delete it.
drop policy if exists "Users insert own unlocks" on public.unlocks;
drop policy if exists "Users update own unlocks" on public.unlocks;
drop policy if exists "Users delete own unlocks" on public.unlocks;

revoke insert, update, delete on table public.unlocks from authenticated, anon, public;
grant select on table public.unlocks to authenticated;

-- The recording token is stored only as a SHA-256 hex digest.
-- No secret value belongs in this file. After you apply it, set the digest once
-- in the SQL editor (replace the placeholder; do not commit the real value):
--
--   insert into private.loan_unlock_gate (id, token_sha256)
--   values (
--     1,
--     encode(extensions.digest(convert_to('PASTE_UNLOCK_RECORD_TOKEN', 'utf8'), 'sha256'), 'hex')
--   )
--   on conflict (id) do update set token_sha256 = excluded.token_sha256;
--
-- Use the same string as the Streamlit secret UNLOCK_RECORD_TOKEN.
-- A missing row fails closed: record_loan_unlock will not write.

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table if not exists private.loan_unlock_gate (
  id integer primary key default 1,
  token_sha256 text not null,
  constraint loan_unlock_gate_singleton check (id = 1)
);

revoke all on table private.loan_unlock_gate from public, anon, authenticated;

create extension if not exists pgcrypto with schema extensions;

create or replace function public.record_loan_unlock(p_session_id text, p_token text)
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

  -- The caller cannot choose whose row is written.
  if p_session_id is null or p_session_id !~ '^cs_[A-Za-z0-9_]+$' or char_length(p_session_id) < 8 then
    raise exception 'invalid session' using errcode = '22023';
  end if;
  if p_token is null or char_length(p_token) < 16 then
    raise exception 'not allowed' using errcode = '42501';
  end if;

  select token_sha256 into expected
  from private.loan_unlock_gate
  where id = 1;

  presented := encode(extensions.digest(convert_to(p_token, 'utf8'), 'sha256'), 'hex');
  if expected is null or presented is distinct from expected then
    raise exception 'not allowed' using errcode = '42501';
  end if;

  -- One Checkout Session cannot unlock a second account.
  if exists (
    select 1
    from public.unlocks
    where stripe_checkout_session_id = p_session_id
      and user_id is distinct from caller
  ) then
    raise exception 'session already used' using errcode = '23505';
  end if;

  if exists (
    select 1
    from public.unlocks
    where user_id = caller
      and product = 'loan_plan_audit'
  ) then
    return;
  end if;

  insert into public.unlocks (
    user_id,
    product,
    stripe_checkout_session_id,
    paid_at,
    terms_accepted_at,
    amount_cents
  ) values (
    caller,
    'loan_plan_audit',
    p_session_id,
    now(),
    now(),
    900
  );
end;
$$;

comment on function public.record_loan_unlock(text, text) is
  'Writes the signed-in user''s loan_plan_audit unlock after the app has checked the Checkout Session with Stripe. The token must match private.loan_unlock_gate. A wrong token does not write.';

revoke all on function public.record_loan_unlock(text, text) from public, anon;
grant execute on function public.record_loan_unlock(text, text) to authenticated;

create or replace function public.delete_my_loan_unlock()
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.uid() is null then
    raise exception 'login required' using errcode = '28000';
  end if;
  delete from public.unlocks
  where user_id = auth.uid()
    and product = 'loan_plan_audit';
end;
$$;

comment on function public.delete_my_loan_unlock() is
  'Deletes only the caller''s loan_plan_audit unlock row. It cannot insert one.';

revoke all on function public.delete_my_loan_unlock() from public, anon;
grant execute on function public.delete_my_loan_unlock() to authenticated;
