-- Add an operator-controlled active/inactive scope to stock and index masters.
-- Existing rows stay eligible for EOD by being backfilled to active.

alter table public.symbols
    add column if not exists status text;

alter table public.index_master
    add column if not exists status text;

update public.symbols
set status = 'active'
where status is null;

update public.index_master
set status = 'active'
where status is null;

alter table public.symbols
    alter column status set default 'active',
    alter column status set not null;

alter table public.index_master
    alter column status set default 'active',
    alter column status set not null;

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.symbols'::regclass
          and conname = 'symbols_status_check'
    ) then
        alter table public.symbols
            add constraint symbols_status_check
            check (status in ('active', 'inactive'));
    end if;

    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.index_master'::regclass
          and conname = 'index_master_status_check'
    ) then
        alter table public.index_master
            add constraint index_master_status_check
            check (status in ('active', 'inactive'));
    end if;
end
$$;

comment on column public.symbols.status is
    'Operator-controlled EOD scope: active rows are included by default; inactive rows require explicit scope.';
comment on column public.index_master.status is
    'Operator-controlled EOD scope: active rows are included by default; inactive rows require explicit scope.';

-- Verification (read only):
-- select status, count(*) from public.symbols group by status order by status;
-- select status, count(*) from public.index_master group by status order by status;
-- select table_name, column_name, is_nullable, column_default
-- from information_schema.columns
-- where table_schema = 'public'
--   and table_name in ('symbols', 'index_master')
--   and column_name = 'status'
-- order by table_name;

-- Rollback (only if no caller depends on status):
-- alter table public.symbols drop column if exists status;
-- alter table public.index_master drop column if exists status;
