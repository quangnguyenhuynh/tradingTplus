from pathlib import Path


SQL = Path("migrations/20260928_rebuild_index_daily_ssi_v3.sql").read_text().lower()
SCHEMA = Path("schema.sql").read_text().lower()


def test_v3_migration_preserves_primary_key_and_raw_evidence():
    assert "index_daily_pkey" in SQL
    assert "delete from public.index_daily" in SQL
    assert "delete from public.index_raw_daily" not in SQL
    assert "drop table" not in SQL
    assert 'primary key ("index_code", "trading_date")' in SCHEMA


def test_v3_migration_has_new_columns_and_removes_legacy_columns():
    expected = (
        "index_change", "index_change_percentage", "total_trade_volume", "total_trade_value",
        "total_match_volume", "total_match_value", "total_deal_volume", "total_deal_value",
        "total_advance_stock", "total_ceiling_stock", "total_decline_stock", "total_floor_stock",
        "total_no_change_stock", "total_prop_buy_volume", "total_prop_buy_value",
        "total_prop_sell_volume", "total_prop_sell_value", "total_foreign_buy_volume",
        "total_foreign_buy_value", "total_foreign_sell_volume", "total_foreign_sell_value",
        "net_foreign_purchase_volume", "net_foreign_purchase_value",
    )
    for column in expected:
        assert f"add column if not exists {column} numeric" in SQL
        assert f'"{column}" numeric' in SCHEMA
    for legacy in ("change", "ratio_change", "total_trade", "total_vol", "type_index", "index_name", "advances"):
        assert f"drop column if exists {legacy}" in SQL
    assert "change → index_change" not in SQL
    assert "set index_change" not in SQL
