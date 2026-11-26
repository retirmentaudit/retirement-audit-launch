-- Scenario history. Do not run this until Jacob approves it.
-- The Streamlit app keeps working if this table is missing.

create table if not exists public.scenarios (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  name text not null default 'My scenario',
  inputs jsonb not null default '{}'::jsonb,
  score integer,
  score_label text,
  monthly_need numeric,
  monthly_need_today numeric,
  monthly_covered numeric,
  percent_covered integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.scenarios is
  'One row each time a signed-in person finishes an audit. Inputs plus the score and income coverage.';

create index if not exists scenarios_user_created_idx
  on public.scenarios (user_id, created_at desc);

alter table public.scenarios enable row level security;

drop policy if exists "Users read own scenarios" on public.scenarios;
create policy "Users read own scenarios"
  on public.scenarios for select
  using (auth.uid() = user_id);

drop policy if exists "Users insert own scenarios" on public.scenarios;
create policy "Users insert own scenarios"
  on public.scenarios for insert
  with check (auth.uid() = user_id);

drop policy if exists "Users update own scenarios" on public.scenarios;
create policy "Users update own scenarios"
  on public.scenarios for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "Users delete own scenarios" on public.scenarios;
create policy "Users delete own scenarios"
  on public.scenarios for delete
  using (auth.uid() = user_id);
