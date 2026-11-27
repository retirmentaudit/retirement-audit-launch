-- Loan Plan Audit tables. Run this in the Supabase SQL editor after review.
-- It is not applied automatically.
-- It does not change public.user_profiles or public.scenarios (Retirement Audit).

create table if not exists public.loan_scenarios (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  name text not null default 'My scenario',
  inputs jsonb not null default '{}'::jsonb,
  summary jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.loan_scenarios is
  'Saved Loan Plan Audit inputs for the signed-in user. The app recomputes results when a row is opened.';

create index if not exists loan_scenarios_user_created_idx
  on public.loan_scenarios (user_id, created_at desc);

alter table public.loan_scenarios enable row level security;
alter table public.loan_scenarios force row level security;

drop policy if exists "Users read own loan scenarios" on public.loan_scenarios;
create policy "Users read own loan scenarios"
  on public.loan_scenarios for select
  to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists "Users insert own loan scenarios" on public.loan_scenarios;
create policy "Users insert own loan scenarios"
  on public.loan_scenarios for insert
  to authenticated
  with check ((select auth.uid()) = user_id);

drop policy if exists "Users update own loan scenarios" on public.loan_scenarios;
create policy "Users update own loan scenarios"
  on public.loan_scenarios for update
  to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists "Users delete own loan scenarios" on public.loan_scenarios;
create policy "Users delete own loan scenarios"
  on public.loan_scenarios for delete
  to authenticated
  using ((select auth.uid()) = user_id);

create table if not exists public.unlocks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  product text not null,
  stripe_checkout_session_id text,
  stripe_customer_id text,
  amount_cents integer,
  terms_accepted_at timestamptz,
  paid_at timestamptz,
  created_at timestamptz not null default now(),
  unique (user_id, product)
);

comment on table public.unlocks is
  'One-time software unlocks, one row per user and product. loan_plan_audit is the $9 report. This is not the Retirement Audit is_paid_user flag.';

create unique index if not exists unlocks_checkout_session_key
  on public.unlocks (stripe_checkout_session_id)
  where stripe_checkout_session_id is not null;

alter table public.unlocks enable row level security;
alter table public.unlocks force row level security;

drop policy if exists "Users read own unlocks" on public.unlocks;
create policy "Users read own unlocks"
  on public.unlocks for select
  to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists "Users insert own unlocks" on public.unlocks;
create policy "Users insert own unlocks"
  on public.unlocks for insert
  to authenticated
  with check ((select auth.uid()) = user_id);

drop policy if exists "Users update own unlocks" on public.unlocks;
create policy "Users update own unlocks"
  on public.unlocks for update
  to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists "Users delete own unlocks" on public.unlocks;
create policy "Users delete own unlocks"
  on public.unlocks for delete
  to authenticated
  using ((select auth.uid()) = user_id);

-- The signed-in user can write their own unlock row after the app has checked
-- the Checkout Session with the Stripe secret. A person with a valid session
-- could insert a row directly. The same limitation exists for Retirement Audit
-- profile updates. The optional webhook in
-- supabase/functions/stripe-checkout-webhook/ is the backup path and uses the
-- service role. Review this before launch.

revoke all on table public.loan_scenarios from anon;
revoke all on table public.unlocks from anon;
grant select, insert, update, delete on table public.loan_scenarios to authenticated;
grant select, insert, update, delete on table public.unlocks to authenticated;
