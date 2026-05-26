create table if not exists public.data_quality_logs (
  id bigserial primary key,
  symbol text not null,
  trading_date date not null,
  check_type text not null,
  status text not null,
  message text,
  missing_count integer,
  expected_count integer,
  actual_count integer,
  created_at timestamptz not null default now()
);

create index if not exists data_quality_logs_symbol_date_idx
on public.data_quality_logs(symbol, trading_date);
