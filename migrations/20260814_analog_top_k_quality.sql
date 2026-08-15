-- Analog nearest-top-k compatibility migration. No rows are rewritten.
-- The profile config hash continues to identify matching semantics.
do $$
declare item record;
begin
  for item in
    select conname
    from pg_constraint
    where conrelid = 'public.analog_profiles'::regclass
      and contype = 'c'
      and pg_get_constraintdef(oid) like '%distance_threshold%'
  loop
    execute format('alter table public.analog_profiles drop constraint %I', item.conname);
  end loop;
end $$;

do $$
declare item record;
begin
  for item in
    select conname
    from pg_constraint
    where conrelid = 'public.analog_query_matches'::regclass
      and contype = 'c'
      and pg_get_constraintdef(oid) like '%rank%30%'
  loop
    execute format('alter table public.analog_query_matches drop constraint %I', item.conname);
  end loop;
end $$;

alter table public.analog_query_matches
  add constraint analog_query_matches_rank_positive check (rank > 0) not valid;
alter table public.analog_query_matches
  validate constraint analog_query_matches_rank_positive;

-- Verification:
-- select conname, pg_get_constraintdef(oid) from pg_constraint
-- where conrelid in ('public.analog_profiles'::regclass,
--                    'public.analog_query_matches'::regclass);
-- Rollback: re-add the former approval/threshold and rank <= 30 checks only after
-- confirming no null-threshold approved profiles and no persisted rank > 30 rows.
