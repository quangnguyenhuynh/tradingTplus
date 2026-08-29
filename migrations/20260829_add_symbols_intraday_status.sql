-- Add operator-controlled scope for automatic 1-minute intraday ingest.
-- Existing symbols retain the pre-split behavior by copying their daily status.

alter table public.symbols
    add column if not exists intraday_status text;

update public.symbols
set intraday_status = status
where intraday_status is null;

alter table public.symbols
    alter column intraday_status set default 'inactive',
    alter column intraday_status set not null;

do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conrelid = 'public.symbols'::regclass
          and conname = 'symbols_intraday_status_check'
    ) then
        alter table public.symbols
            add constraint symbols_intraday_status_check
            check (intraday_status in ('active', 'inactive'));
    end if;
end
$$;

comment on column public.symbols.intraday_status is
    'Operator-controlled scope for automatic intraday ingest; effective scope also requires status=active.';

-- Verification (read only):
-- select status, intraday_status, count(*) from public.symbols group by status, intraday_status order by status, intraday_status;
-- select column_name, is_nullable, column_default from information_schema.columns
-- where table_schema = 'public' and table_name = 'symbols' and column_name = 'intraday_status';
-- select conname, pg_get_constraintdef(oid) from pg_constraint
-- where conrelid = 'public.symbols'::regclass and conname = 'symbols_intraday_status_check';

-- Rollback (only before application callers depend on the column):
-- alter table public.symbols drop constraint if exists symbols_intraday_status_check;
-- alter table public.symbols drop column if exists intraday_status;
