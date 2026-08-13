-- Historical Analog Core EOD V2: allow normalized H+10 outcome rows.
-- Additive/manual migration. V1 rows and identities remain unchanged; no column
-- is added and public.analog_outcomes is never recreated or emptied.

do $$
declare
  constraint_name text;
begin
  if to_regclass('public.analog_outcomes') is null then
    raise exception 'public.analog_outcomes is missing; apply the Analog V1 creation or recovery migration first';
  end if;

  for constraint_name in
    select con.conname
    from pg_constraint con
    join pg_class rel on rel.oid = con.conrelid
    join pg_namespace nsp on nsp.oid = rel.relnamespace
    where nsp.nspname = 'public'
      and rel.relname = 'analog_outcomes'
      and con.contype = 'c'
      and pg_get_constraintdef(con.oid) ilike '%horizon_sessions%'
  loop
    execute format(
      'alter table public.analog_outcomes drop constraint if exists %I',
      constraint_name
    );
  end loop;

  if not exists (
    select 1
    from pg_constraint con
    join pg_class rel on rel.oid = con.conrelid
    join pg_namespace nsp on nsp.oid = rel.relnamespace
    where nsp.nspname = 'public'
      and rel.relname = 'analog_outcomes'
      and con.conname = 'analog_outcomes_horizon_sessions_check'
  ) then
    alter table public.analog_outcomes
      add constraint analog_outcomes_horizon_sessions_check
      check (horizon_sessions in (1, 3, 5, 10));
  end if;
end $$;

comment on constraint analog_outcomes_horizon_sessions_check
  on public.analog_outcomes is
  'Allows EOD V1 H+1/H+3/H+5 and EOD V2 H+1/H+3/H+5/H+10 normalized outcome rows.';

-- Verification (run manually after deployment):
-- select pg_get_constraintdef(oid) from pg_constraint
-- where conrelid = 'public.analog_outcomes'::regclass
--   and conname = 'analog_outcomes_horizon_sessions_check';
-- select horizon_sessions, count(*) from public.analog_outcomes
-- group by horizon_sessions order by horizon_sessions;
--
-- Rollback guidance: remove V2 H+10 rows only after confirming their exact V2
-- snapshot identity, then replace this constraint with (1,3,5). Never delete or
-- rewrite V1 rows. Adding/checking this constraint takes a table lock and scans
-- existing rows; schedule the manual deployment accordingly.
