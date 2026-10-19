-- Screener V2: immutable executable configuration + bilingual human methodology.
-- Apply manually AFTER 20261017_create_stock_screener_results.sql.
create table if not exists public.screener_configs (
    screener_version text primary key,
    config_hash text not null,
    config jsonb not null,
    methodology_md text not null,
    methodology_vi_md text not null,
    created_at timestamptz not null,
    constraint screener_configs_hash_format check (config_hash ~ '^[0-9a-f]{64}$'),
    constraint screener_configs_config_object check (jsonb_typeof(config) = 'object'),
    constraint screener_configs_docs_present check (
        length(trim(methodology_md)) > 0 and length(trim(methodology_vi_md)) > 0
    ),
    unique (screener_version, config_hash)
);
alter table public.screener_configs enable row level security;
revoke all on public.screener_configs from anon, authenticated;

-- Immutable registry: do not silently overwrite configuration or methodology for a version.
create or replace function public.guard_screener_config_immutable()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
    raise exception 'screener_configs versions are immutable; create a new version';
end;
$$;
drop trigger if exists screener_configs_immutable_guard on public.screener_configs;
create trigger screener_configs_immutable_guard
before update or delete on public.screener_configs
for each row execute function public.guard_screener_config_immutable();

alter table public.stock_screener_results
    add column if not exists config_hash text;
alter table public.stock_screener_results
    add constraint stock_screener_results_v2_config_required
    check (screener_version <> 'v2' or config_hash is not null);
alter table public.stock_screener_results
    add constraint stock_screener_results_config_fk
    foreign key (screener_version, config_hash)
    references public.screener_configs(screener_version, config_hash);

comment on column public.stock_screener_results.config_hash is
'Exact SHA256 identity of executable config and EN/VI methodology; NULL for legacy V1.';

-- VERIFY after manual deployment:
-- select column_name from information_schema.columns
-- where table_schema='public' and table_name='stock_screener_results'
-- and column_name='config_hash';
-- select relname,relrowsecurity from pg_class
-- where relname in ('screener_configs','stock_screener_results');
-- select conname from pg_constraint
-- where conrelid='public.stock_screener_results'::regclass;

-- IMPACT: additive metadata table and nullable column, no rewrite of V1 scores/data.
-- CONFIG REGISTRATION: python main.py stock-screener-config --version v2 --apply
-- BACKFILL: none required. Explicit V2 screener runs may be performed afterward.
-- Lock risk: ADD COLUMN/CONSTRAINT takes a brief ACCESS EXCLUSIVE lock on results;
-- new FK validation scans existing rows (legacy V1 hash is NULL). Plan maintenance.
-- ROLLBACK: only if no V2 results need retention; drop FK/check/column first,
-- then function/trigger and configs table. Export V2 rows/config before rollback.
