-- Recovery for a partially applied 20260809 Analog migration. Additive/idempotent; preserves rows.
create or replace function public.analog_jsonb_object_size(value jsonb) returns integer
language sql immutable strict parallel safe set search_path to ''
as $$ select count(*)::integer from jsonb_object_keys(value) $$;
revoke all on function public.analog_jsonb_object_size(jsonb) from public,anon,authenticated;
grant execute on function public.analog_jsonb_object_size(jsonb) to service_role;

-- Phase 1 Historical Analog Core EOD V1. Additive only; apply manually.
create table if not exists public.analog_profiles (
  profile_code text not null, version integer not null check (version > 0), config_hash text not null check (config_hash ~ '^[0-9a-f]{64}$'),
  configuration jsonb not null, status text not null check (status in ('draft','validated','approved','rejected','retired')) default 'draft',
  registered_at timestamptz not null, status_changed_at timestamptz not null,
  primary key (profile_code, version), unique (profile_code, version, config_hash),
  check (configuration->>'profile_code'=profile_code and (configuration->>'version')::integer=version),
  check (status <> 'approved' or jsonb_typeof(configuration->'distance_threshold')='number')
);

create table if not exists public.analog_snapshots (
  id uuid primary key default extensions.gen_random_uuid(), profile_code text not null, version integer not null, config_hash text not null,
  symbol text not null references public.symbols(symbol), timeframe text not null check (timeframe='1d'), checkpoint text not null check (checkpoint='EOD'), trading_session date not null,
  dimensions jsonb not null, input_fingerprint text not null check (input_fingerprint ~ '^[0-9a-f]{64}$'),
  evaluation_status text not null check (evaluation_status in ('evaluable','not_evaluable','invalid','excluded')), invalid_reason_codes jsonb not null default '[]'::jsonb check (jsonb_typeof(invalid_reason_codes)='array'),
  created_at timestamptz not null, updated_at timestamptz not null,
  foreign key (profile_code,version,config_hash) references public.analog_profiles(profile_code,version,config_hash),
  unique(profile_code,version,config_hash,symbol,timeframe,checkpoint,trading_session),
  check (evaluation_status <> 'evaluable' or (public.analog_jsonb_object_size(dimensions)=9 and dimensions ?& array['return_5d','price_vs_ema20_pct','ema20_vs_ema50_pct','rsi14','macd_histogram_pct','distance_to_high20_pct','volume_ratio','value_ratio','close_position_in_candle']))
);

create table if not exists public.analog_outcomes (
  id uuid primary key default extensions.gen_random_uuid(), snapshot_id uuid not null references public.analog_snapshots(id) on delete cascade,
  horizon_sessions integer not null check (horizon_sessions in (1,3,5)), reference_session date, reference_close double precision,
  target_session date, target_close double precision, return_ratio double precision,
  status text not null check (status in ('pending','completed','unavailable')), unavailable_reason text, created_at timestamptz not null, updated_at timestamptz not null,
  unique(snapshot_id,horizon_sessions), check (status <> 'completed' or (target_session is not null and reference_close > 0 and target_close is not null and return_ratio is not null))
);

create table if not exists public.analog_validation_runs (
  id uuid primary key default extensions.gen_random_uuid(), profile_code text not null, version integer not null, config_hash text not null,
  run_type text not null check (run_type in ('calibration','validation','final')), training_range daterange, validation_range daterange, final_test_range daterange, data_cutoff date not null,
  parameters jsonb not null default '{}'::jsonb, code_revision text, status text not null check(status in ('running','completed','failed')),
  metrics jsonb, artifacts jsonb, errors jsonb, started_at timestamptz not null, completed_at timestamptz,
  foreign key(profile_code,version,config_hash) references public.analog_profiles(profile_code,version,config_hash)
);

create table if not exists public.analog_profile_reviews (
  id uuid primary key default extensions.gen_random_uuid(), profile_code text not null, version integer not null, config_hash text not null,
  validation_run_id uuid not null references public.analog_validation_runs(id), reviewer text not null, decision text not null check(decision in ('approve','reject')), reason text not null, decided_at timestamptz not null,
  foreign key(profile_code,version,config_hash) references public.analog_profiles(profile_code,version,config_hash),
  unique(profile_code,version,config_hash,validation_run_id,reviewer,decision)
);

create table if not exists public.analog_queries (
  id uuid primary key default extensions.gen_random_uuid(), snapshot_id uuid not null references public.analog_snapshots(id), profile_code text not null, version integer not null, config_hash text not null,
  symbol text not null, timeframe text not null check(timeframe='1d'), checkpoint text not null check(checkpoint='EOD'), as_of_session date not null,
  status text not null check(status in ('completed','insufficient_sample','not_evaluable','blocked')), candidate_count integer not null check(candidate_count>=0), usable_sample integer not null check(usable_sample>=0),
  normalization_parameters jsonb, result_statistics jsonb, baseline_statistics jsonb, input_fingerprint text not null, query_fingerprint text not null,
  engine_version text, executed_at timestamptz not null,
  foreign key(profile_code,version,config_hash) references public.analog_profiles(profile_code,version,config_hash),
  unique(profile_code,version,config_hash,symbol,checkpoint,as_of_session,query_fingerprint)
);

create table if not exists public.analog_query_matches (
  query_id uuid not null references public.analog_queries(id) on delete cascade, rank integer not null check(rank between 1 and 30), matched_snapshot_id uuid not null references public.analog_snapshots(id),
  distance double precision not null check(distance>=0), similarity double precision not null check(similarity between 0 and 100), normalized_differences jsonb,
  primary key(query_id,rank), unique(query_id,matched_snapshot_id)
);

create index if not exists analog_snapshots_symbol_session_idx on public.analog_snapshots(symbol,trading_session desc,profile_code,version,config_hash);
create index if not exists analog_outcomes_target_status_idx on public.analog_outcomes(target_session,status,horizon_sessions);
create index if not exists analog_validation_identity_idx on public.analog_validation_runs(profile_code,version,config_hash,run_type,status);
create index if not exists analog_reviews_identity_idx on public.analog_profile_reviews(profile_code,version,config_hash,decided_at desc);
create index if not exists analog_queries_latest_idx on public.analog_queries(symbol,checkpoint,as_of_session desc);
create index if not exists analog_matches_snapshot_idx on public.analog_query_matches(matched_snapshot_id);

alter table public.analog_profiles enable row level security; alter table public.analog_snapshots enable row level security;
alter table public.analog_outcomes enable row level security; alter table public.analog_validation_runs enable row level security;
alter table public.analog_profile_reviews enable row level security; alter table public.analog_queries enable row level security;
alter table public.analog_query_matches enable row level security;
revoke all on public.analog_profiles,public.analog_snapshots,public.analog_outcomes,public.analog_validation_runs,public.analog_profile_reviews,public.analog_queries,public.analog_query_matches from anon,authenticated,public;
grant select on public.analog_profiles,public.analog_queries,public.analog_query_matches to authenticated;
grant all on public.analog_profiles,public.analog_snapshots,public.analog_outcomes,public.analog_validation_runs,public.analog_profile_reviews,public.analog_queries,public.analog_query_matches to service_role;
drop policy if exists analog_profiles_authenticated_read on public.analog_profiles;
drop policy if exists analog_queries_authenticated_read on public.analog_queries;
drop policy if exists analog_matches_authenticated_read on public.analog_query_matches;
drop policy if exists analog_profiles_service on public.analog_profiles;
drop policy if exists analog_snapshots_service on public.analog_snapshots;
drop policy if exists analog_outcomes_service on public.analog_outcomes;
drop policy if exists analog_validation_service on public.analog_validation_runs;
drop policy if exists analog_reviews_service on public.analog_profile_reviews;
drop policy if exists analog_queries_service on public.analog_queries;
drop policy if exists analog_matches_service on public.analog_query_matches;
create policy analog_profiles_authenticated_read on public.analog_profiles for select to authenticated using (status='approved');
create policy analog_queries_authenticated_read on public.analog_queries for select to authenticated using (status in ('completed','insufficient_sample','not_evaluable'));
create policy analog_matches_authenticated_read on public.analog_query_matches for select to authenticated using (exists(select 1 from public.analog_queries q where q.id=query_id and q.status in ('completed','insufficient_sample','not_evaluable')));
create policy analog_profiles_service on public.analog_profiles for all to service_role using(true) with check(true);
create policy analog_snapshots_service on public.analog_snapshots for all to service_role using(true) with check(true);
create policy analog_outcomes_service on public.analog_outcomes for all to service_role using(true) with check(true);
create policy analog_validation_service on public.analog_validation_runs for all to service_role using(true) with check(true);
create policy analog_reviews_service on public.analog_profile_reviews for all to service_role using(true) with check(true);
create policy analog_queries_service on public.analog_queries for all to service_role using(true) with check(true);
create policy analog_matches_service on public.analog_query_matches for all to service_role using(true) with check(true);


-- Atomic and retry-safe query header + complete match persistence.
create or replace function public.persist_analog_query_v1(p_query jsonb, p_matches jsonb)
returns setof public.analog_queries
language plpgsql security definer set search_path to '' as $$
declare v_query public.analog_queries; v_count integer;
begin
  if jsonb_typeof(p_query) <> 'object' or jsonb_typeof(p_matches) <> 'array' then
    raise exception 'query must be an object and matches must be an array';
  end if;
  insert into public.analog_queries(snapshot_id,profile_code,version,config_hash,symbol,timeframe,checkpoint,as_of_session,status,candidate_count,usable_sample,normalization_parameters,result_statistics,baseline_statistics,input_fingerprint,query_fingerprint,engine_version,executed_at)
  select x.snapshot_id,x.profile_code,x.version,x.config_hash,x.symbol,x.timeframe,x.checkpoint,x.as_of_session,x.status,x.candidate_count,x.usable_sample,x.normalization_parameters,x.result_statistics,x.baseline_statistics,x.input_fingerprint,x.query_fingerprint,x.engine_version,x.executed_at
  from jsonb_to_record(p_query) x(snapshot_id uuid,profile_code text,version integer,config_hash text,symbol text,timeframe text,checkpoint text,as_of_session date,status text,candidate_count integer,usable_sample integer,normalization_parameters jsonb,result_statistics jsonb,baseline_statistics jsonb,input_fingerprint text,query_fingerprint text,engine_version text,executed_at timestamptz)
  on conflict(profile_code,version,config_hash,symbol,checkpoint,as_of_session,query_fingerprint)
  do update set executed_at=excluded.executed_at
  returning * into v_query;
  insert into public.analog_query_matches(query_id,rank,matched_snapshot_id,distance,similarity,normalized_differences)
  select v_query.id,x.rank,x.matched_snapshot_id,x.distance,x.similarity,x.normalized_differences
  from jsonb_to_recordset(p_matches) x(rank integer,matched_snapshot_id uuid,distance double precision,similarity double precision,normalized_differences jsonb)
  on conflict(query_id,rank) do update set matched_snapshot_id=excluded.matched_snapshot_id,distance=excluded.distance,similarity=excluded.similarity,normalized_differences=excluded.normalized_differences;
  get diagnostics v_count = row_count;
  if v_count <> jsonb_array_length(p_matches) then raise exception 'match count mismatch'; end if;
  return next v_query;
end $$;
revoke all on function public.persist_analog_query_v1(jsonb,jsonb) from public,anon,authenticated;
grant execute on function public.persist_analog_query_v1(jsonb,jsonb) to service_role;
