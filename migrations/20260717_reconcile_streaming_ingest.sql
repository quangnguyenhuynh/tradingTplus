-- Reconcile SSI streaming ingest schema for Issue #73.
-- Additive/idempotent only: no drop, truncate, or data deletion.

create table if not exists public.stream_raw_snapshot (
    id bigserial primary key,
    channel text not null,
    rtype text,
    symbol text,
    index_code text,
    time timestamptz,
    trading_date date,
    payload jsonb not null,
    created_at timestamptz default now()
);

alter table if exists public.stream_raw_snapshot
    add column if not exists requested_channel text,
    add column if not exists source_time timestamptz,
    add column if not exists received_at timestamptz,
    add column if not exists payload_hash text,
    add column if not exists validation_status text,
    add column if not exists validation_issues jsonb default '[]'::jsonb;

update public.stream_raw_snapshot
set received_at = coalesce(received_at, created_at, time)
where received_at is null;

update public.stream_raw_snapshot
set source_time = coalesce(source_time, time)
where source_time is null and time is not null;

update public.stream_raw_snapshot
set requested_channel = coalesce(requested_channel, channel)
where requested_channel is null;

update public.stream_raw_snapshot
set validation_status = coalesce(validation_status, 'UNKNOWN')
where validation_status is null;

update public.stream_raw_snapshot
set validation_issues = '[]'::jsonb
where validation_issues is null;

create unique index if not exists ux_stream_raw_snapshot_payload_hash
on public.stream_raw_snapshot(payload_hash);

create table if not exists public.stream_status_snapshot (
    symbol text not null,
    time timestamptz not null,
    trading_date date,
    exchange text,
    market_id text,
    trading_session text,
    trading_status text,
    raw jsonb,
    created_at timestamptz default now()
);
create unique index if not exists ux_stream_status_snapshot_symbol_time
on public.stream_status_snapshot(symbol, time);

create table if not exists public.stream_bar_snapshot (
    symbol text not null,
    time timestamptz not null,
    trading_date date,
    exchange text,
    market_id text,
    open double precision,
    high double precision,
    low double precision,
    close double precision,
    volume bigint,
    value bigint,
    raw jsonb,
    created_at timestamptz default now()
);
create unique index if not exists ux_stream_bar_snapshot_symbol_time
on public.stream_bar_snapshot(symbol, time);

create table if not exists public.stream_quote_snapshot (
    symbol text not null,
    time timestamptz not null,
    trading_date date,
    raw jsonb,
    created_at timestamptz default now()
);
create unique index if not exists ux_stream_quote_snapshot_symbol_time on public.stream_quote_snapshot(symbol, time);

create table if not exists public.stream_trade_snapshot (
    symbol text not null,
    time timestamptz not null,
    trading_date date,
    raw jsonb,
    created_at timestamptz default now()
);
create unique index if not exists ux_stream_trade_snapshot_symbol_time on public.stream_trade_snapshot(symbol, time);

create table if not exists public.stream_foreign_snapshot (
    symbol text not null,
    time timestamptz not null,
    trading_date date,
    raw jsonb,
    created_at timestamptz default now()
);
create unique index if not exists ux_stream_foreign_snapshot_symbol_time on public.stream_foreign_snapshot(symbol, time);

create table if not exists public.stream_index_snapshot (
    index_code text not null,
    time timestamptz not null,
    trading_date date,
    raw jsonb,
    created_at timestamptz default now()
);
create unique index if not exists ux_stream_index_snapshot_index_code_time on public.stream_index_snapshot(index_code, time);

-- Verification SQL:
-- select tablename, indexname, indexdef from pg_indexes where schemaname='public' and tablename like 'stream_%_snapshot' order by tablename,indexname;
-- select table_name, column_name, data_type from information_schema.columns where table_schema='public' and table_name in ('stream_raw_snapshot','stream_quote_snapshot','stream_trade_snapshot','stream_foreign_snapshot','stream_index_snapshot','stream_status_snapshot','stream_bar_snapshot') order by table_name, ordinal_position;
