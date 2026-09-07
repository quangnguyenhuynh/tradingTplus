from pathlib import Path
SQL=Path("migrations/20260907_create_stock_foreign_features_daily.sql").read_text()
def test_security_and_contract():
    assert "security invoker" in SQL.lower()
    assert "revoke all on function" in SQL.lower()
    assert "from public, anon" in SQL.lower()
    assert "primary key(symbol,trading_date)" in SQL.lower()
    assert "left join public.stock_foreign_features_daily" in SQL.lower()
    assert "coverage_ratio" in SQL and "rank() over" in SQL.lower()
