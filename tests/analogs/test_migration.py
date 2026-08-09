from pathlib import Path

SQL = Path("migrations/20260809_create_historical_analog_core_eod_v1.sql").read_text()
TABLES = (
    "analog_profiles",
    "analog_snapshots",
    "analog_outcomes",
    "analog_validation_runs",
    "analog_profile_reviews",
    "analog_queries",
    "analog_query_matches",
)


def test_seven_tables_constraints_indexes_and_rls():
    assert all(f"create table if not exists public.{table}" in SQL for table in TABLES)
    assert SQL.count("enable row level security") == 7
    assert "grant all on public.analog_profiles" in SQL and "to service_role" in SQL
    assert "revoke all on public.analog_profiles" in SQL
    assert (
        "unique(profile_code,version,config_hash,symbol,timeframe,checkpoint,trading_session)"
        in SQL
    )
    assert "unique(snapshot_id,horizon_sessions)" in SQL
    assert "unique(query_id,matched_snapshot_id)" in SQL


def test_migration_does_not_change_phase0_or_legacy_tables():
    lowered = SQL.lower()
    for operation in (
        "alter table public.features",
        "drop table",
        "truncate",
        "delete from",
    ):
        assert operation not in lowered
