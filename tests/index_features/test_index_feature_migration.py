from pathlib import Path

SQL = Path("migrations/20260826_create_index_features_daily.sql").read_text()


def test_migration_has_identity_fk_columns_and_service_only_rls():
    assert "create table if not exists public.index_features_daily" in SQL
    assert "primary key (index_code, trading_date)" in SQL
    assert "references public.index_master(index_code)" in SQL
    for column in ("index_return_10d", "index_drawdown_60d", "index_breadth_ma10", "index_deal_val_ratio"):
        assert column in SQL
    assert "enable row level security" in SQL
    assert "revoke all on table public.index_features_daily from anon, authenticated" in SQL
    assert "grant all on table public.index_features_daily to service_role" in SQL
    assert "alter table public.features" not in SQL


def test_exact_source_context_uses_numeric_and_ratios_use_float():
    for column in ("index_value numeric", "total_vol numeric", "total_val numeric", "breadth_total numeric"):
        assert column in SQL
    assert "index_breadth_ratio double precision" in SQL
    assert "created_at timestamptz not null default now()" in SQL
    assert "updated_at timestamptz not null default now()" in SQL
