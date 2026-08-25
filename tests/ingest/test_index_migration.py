from pathlib import Path


SQL = Path("migrations/20260825_standardize_index_daily_pipeline.sql").read_text()


def test_index_migration_has_guarded_rename_raw_identity_and_clean_transition():
    assert "both public.indexes and public.index_master exist" in SQL
    assert "alter table public.indexes rename to index_master" in SQL
    assert "index_raw_daily(index_code,trading_date,data_hash)" in SQL
    assert "SSI_DailyIndex_legacy" in SQL
    assert "alter table public.index_daily drop column if exists raw" in SQL
    assert "fetched_at timestamptz null" in SQL
