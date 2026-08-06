-- Correct Phase 1 signal identity without deleting existing evidence.
alter table public.signals add column if not exists signal_session date;

update public.signals
set signal_session = (signal_time at time zone 'Asia/Ho_Chi_Minh')::date
where signal_session is null;

do $$
begin
  if exists (
    select 1 from public.signals
    group by strategy_code, strategy_version, config_hash, symbol, signal_session
    having count(*) > 1
  ) then raise exception 'Phase 1 live duplicate-session evidence exists; reconcile explicitly before creating first-match index'; end if;
  if exists (
    select 1 from public.backtest_signals
    group by backtest_run_id, strategy_code, strategy_version, config_hash, symbol, entry_session
    having count(*) > 1
  ) then raise exception 'Phase 1 backtest duplicate-session evidence exists; reconcile explicitly before creating first-match index'; end if;
end $$;

alter table public.signals alter column signal_session set not null;
create unique index if not exists signals_first_match_session_uidx
  on public.signals(strategy_code, strategy_version, config_hash, symbol, signal_session);
create unique index if not exists backtest_signals_first_match_session_uidx
  on public.backtest_signals(backtest_run_id, strategy_code, strategy_version, config_hash, symbol, entry_session);

-- Verification SQL:
-- select indexname,indexdef from pg_indexes where indexname in
-- ('signals_first_match_session_uidx','backtest_signals_first_match_session_uidx');
-- select count(*) from public.signals where signal_session is null; -- expect 0
-- Rollback/cleanup guidance: stop Phase 1 writers, then drop the two indexes.
-- The column may be retained safely; drop it only after reverting all writers.
