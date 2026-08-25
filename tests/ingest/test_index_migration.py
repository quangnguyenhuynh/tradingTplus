from pathlib import Path


SQL = Path("migrations/20260825_standardize_index_daily_pipeline.sql").read_text()


def test_index_migration_has_guarded_rename_raw_identity_and_clean_transition():
    assert "both public.indexes and public.index_master exist" in SQL
    assert "alter table public.indexes rename to index_master" in SQL
    assert "index_raw_daily(index_code,trading_date,data_hash)" in SQL
    assert "SSI_DailyIndex_legacy" in SQL
    assert "alter table public.index_daily drop column if exists raw" in SQL
    assert "fetched_at timestamptz null" in SQL


def test_index_raw_daily_payload_satisfies_all_committed_not_null_columns():
    table_ddl = SQL.split("create table if not exists public.index_raw_daily (", 1)[1].split(
        ");", 1
    )[0]
    required = {
        line.strip().split()[0]
        for line in table_ddl.splitlines()
        if "not null" in line
    }
    row = {
        "index_code": "VNINDEX",
        "trading_date": "2026-08-24",
        "data_hash": "hash",
        "payload": {"IndexId": "VNINDEX"},
        "source": "SSI_DailyIndex",
        "created_at": "2026-08-25T00:00:00+00:00",
    }
    assert required == {
        "index_code", "trading_date", "data_hash", "payload", "source", "created_at"
    }
    assert all(column in row and row[column] is not None for column in required)
