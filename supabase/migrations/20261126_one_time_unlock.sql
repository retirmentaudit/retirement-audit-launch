-- One-time $5 unlock columns for public.user_profiles.
-- Run this in the Supabase SQL editor. It is safe to run more than once.
-- The Streamlit app reads and writes these columns with the logged-in user's
-- session, the same way it already reads is_paid_user and subscription_status.

alter table public.user_profiles
  add column if not exists paid_via text,
  add column if not exists stripe_checkout_session_id text,
  add column if not exists stripe_customer_id text,
  add column if not exists paid_at timestamptz,
  add column if not exists ai_questions_used integer not null default 0;

comment on column public.user_profiles.paid_via is
  'one_time for a $5 payment. subscription is only a marker for a profile that was already paid before this unlock; the app does not sell a subscription.';
comment on column public.user_profiles.stripe_checkout_session_id is
  'Checkout Session id already applied. A repeat visit with the same id does not write again.';
comment on column public.user_profiles.stripe_customer_id is
  'Stripe customer id when Checkout created one. Existing subscription rows may already have this.';
comment on column public.user_profiles.paid_at is
  'When a one-time unlock was first recorded. Left unchanged if it is already set.';
comment on column public.user_profiles.ai_questions_used is
  'AI questions answered for this account. Free cap is 3. Paid cap is 50.';

create unique index if not exists user_profiles_stripe_checkout_session_id_key
  on public.user_profiles (stripe_checkout_session_id)
  where stripe_checkout_session_id is not null;

-- Anyone who already paid stays unlocked. Mark active and trialing rows, and
-- remember that those profiles were paid before the $5 unlock. The app does
-- not start a new subscription.
update public.user_profiles
set is_paid_user = true,
    paid_via = coalesce(paid_via, 'subscription')
where lower(coalesce(subscription_status, '')) in ('active', 'trialing');

update public.user_profiles
set paid_via = 'subscription'
where paid_via is null
  and coalesce(is_paid_user, false) = true;

-- The app updates the signed-in user's own row after checkout and after each
-- saved AI question. If those updates are rejected, the row's policies do not
-- allow the user to update their own profile. Review this against the policies
-- you already have before enabling it. It is not applied by this file.
--
-- create policy "users update own profile"
--   on public.user_profiles for update
--   using (auth.uid() = user_id)
--   with check (auth.uid() = user_id);
