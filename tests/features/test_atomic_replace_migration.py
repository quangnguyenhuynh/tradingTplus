from pathlib import Path


def test_atomic_replace_migration_is_scoped_transactional_and_service_role_only():
    sql = Path("migrations/20260802_atomic_replace_features.sql").read_text().lower()
    assert "create or replace function public.replace_features_atomic" in sql
    assert "security definer" in sql
    assert "set search_path = ''" in sql
    assert "delete from public.features" in sql
    assert "symbol = p_symbol" in sql
    assert "timeframe = p_timeframe" in sql
    assert "time >= p_start_utc" in sql
    assert "time < p_end_exclusive_utc" in sql
    assert "jsonb_array_length(p_replacement_rows) = 0" in sql
    assert "revoke all on function" in sql
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql


def test_schema_snapshot_contains_atomic_replace_signature():
    schema = Path("schema.sql").read_text()
    assert 'FUNCTION "public"."replace_features_atomic"' in schema
    assert 'GRANT EXECUTE ON FUNCTION "public"."replace_features_atomic"' in schema
