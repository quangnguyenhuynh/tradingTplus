-- Correct the canonical stock_daily room name without changing market values.
-- This is safe when production was already renamed manually. If both names
-- exist, stop for operator review rather than choosing or overwriting data.
begin;
set local lock_timeout = '5s';
set local statement_timeout = '5min';

do $$
declare
  old_column_exists boolean;
  new_column_exists boolean;
begin
  select exists (
    select 1 from information_schema.columns
    where table_schema = 'public'
      and table_name = 'stock_daily'
      and column_name = 'foreign_current_room'
  ) into old_column_exists;

  select exists (
    select 1 from information_schema.columns
    where table_schema = 'public'
      and table_name = 'stock_daily'
      and column_name = 'foreign_remaining_room'
  ) into new_column_exists;

  if old_column_exists and new_column_exists then
    raise exception using
      message = 'Ambiguous stock_daily schema: both foreign_current_room and foreign_remaining_room exist',
      hint = 'Review both columns and reconcile their data before rerunning this migration.';
  elsif old_column_exists and not new_column_exists then
    alter table public.stock_daily
      rename column foreign_current_room to foreign_remaining_room;
  end if;
end $$;

notify pgrst, 'reload schema';
commit;

-- Verification (read-only):
-- select column_name, data_type
-- from information_schema.columns
-- where table_schema = 'public' and table_name = 'stock_daily'
--   and column_name in ('foreign_current_room', 'foreign_remaining_room', 'foreign_total_room')
-- order by column_name;
-- Expected: foreign_remaining_room and foreign_total_room only, both numeric.
-- No backfill is required: PostgreSQL RENAME COLUMN preserves existing values.
-- Rollback: rename foreign_remaining_room back only if foreign_current_room is
-- absent and all deployed application writers have first been rolled back.
