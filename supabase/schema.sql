-- Supabase schema for Daily arXiv Recommender.
-- Run this in the Supabase SQL editor for the project used by the GitHub Pages site.

create table if not exists public.feedback_events (
  id uuid primary key default gen_random_uuid(),
  paper_id text not null,
  rating text not null check (rating in ('like', 'dislike')),
  source text not null default 'page' check (source in ('page', 'email')),
  section text,
  title text,
  abstract text,
  authors jsonb not null default '[]'::jsonb,
  affiliations jsonb not null default '[]'::jsonb,
  categories jsonb not null default '[]'::jsonb,
  user_agent text,
  created_at timestamptz not null default now()
);

create index if not exists feedback_events_paper_id_idx
  on public.feedback_events (paper_id);

create index if not exists feedback_events_created_at_idx
  on public.feedback_events (created_at desc);

create table if not exists public.recommendation_runs (
  id uuid primary key default gen_random_uuid(),
  run_date date not null,
  paper_id text not null,
  rank integer not null,
  score double precision not null,
  section text,
  shown_in_email boolean not null default false,
  shown_on_page boolean not null default true,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (run_date, paper_id)
);

create index if not exists recommendation_runs_run_date_idx
  on public.recommendation_runs (run_date desc);

create table if not exists public.profile_state (
  id text primary key default 'default',
  updated_at timestamptz not null default now(),
  liked_keywords jsonb not null default '[]'::jsonb,
  disliked_keywords jsonb not null default '[]'::jsonb,
  liked_authors jsonb not null default '[]'::jsonb,
  section_weights jsonb not null default '{}'::jsonb,
  embedding_summary jsonb not null default '{}'::jsonb
);

alter table public.feedback_events enable row level security;
alter table public.recommendation_runs enable row level security;
alter table public.profile_state enable row level security;

drop policy if exists feedback_events_public_insert on public.feedback_events;
create policy feedback_events_public_insert
  on public.feedback_events
  for insert
  to anon
  with check (
    rating in ('like', 'dislike')
    and source in ('page', 'email')
    and length(paper_id) between 1 and 256
  );

drop policy if exists feedback_events_no_public_read on public.feedback_events;
create policy feedback_events_no_public_read
  on public.feedback_events
  for select
  to anon
  using (false);

drop policy if exists recommendation_runs_no_public_read on public.recommendation_runs;
create policy recommendation_runs_no_public_read
  on public.recommendation_runs
  for select
  to anon
  using (false);

drop policy if exists profile_state_no_public_read on public.profile_state;
create policy profile_state_no_public_read
  on public.profile_state
  for select
  to anon
  using (false);
