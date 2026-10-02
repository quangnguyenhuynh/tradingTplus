from pathlib import Path

from scripts.check_ssi_ingest_schema import REQUIRED_COLUMNS, REQUIRED_UNIQUE_INDEXES


def test_stock_daily_v3_migration_and_schema_contract_are_present():
    sql = Path("migrations/20261002_promote_stock_daily_ssi_v3.sql").read_text().lower()
    assert "add column if not exists foreign_total_room numeric" in sql
    assert "add column if not exists source text" in sql
    assert "add column if not exists fetched_at timestamptz" in sql
    assert "set source = 'ssi_v2'" in sql
    assert "set fetched_at = created_at" in sql
    assert "alter column source set not null" in sql
    assert "(symbol, trading_date, source, data_hash)" in sql
    assert "foreign_total_room" in REQUIRED_COLUMNS["stock_daily"]
    assert {"source", "fetched_at"} <= set(REQUIRED_COLUMNS["stock_raw_daily"])
    assert "symbol, trading_date, source, data_hash" in REQUIRED_UNIQUE_INDEXES["stock_raw_daily"]
