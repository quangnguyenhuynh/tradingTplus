from pathlib import Path

V1 = Path("migrations/20260907_create_stock_foreign_features_daily.sql").read_text()
V2 = Path("migrations/20260923_foreign_features_symbol_rows_v2.sql").read_text()


def test_base_table_security_and_conflict_contract_remains():
    assert "primary key(symbol,trading_date)" in V1.lower()
    assert "security invoker" in V1.lower()


def test_v2_rpc_contract_uses_symbol_rows_and_version_two_without_calendar():
    sql = V2.lower()
    assert sql.count("security invoker") == 2
    assert "formula_version=2" in sql and "'formula_version',2" in sql
    assert "window_basis','symbol_rows'" in sql
    assert "quality_status->'calendar'" not in sql
    assert "sessions" not in sql
    assert "limit 10" in sql and "emerging_valid_rows=10" in sql
    assert "previous_activity_value_5d" in sql and "previous_activity_ratio_5d" in sql


def test_v2_preserves_rpc_signatures_and_privileges_and_documents_verification():
    sql = V2.lower()
    assert "create or replace function public.get_foreign_ranking(" in sql
    assert "create or replace function public.get_foreign_symbol_history(" in sql
    assert "revoke all on function" in sql and "from public,anon" in sql
    assert "to authenticated,service_role" in sql
    assert "verification (read-only" in sql and "rollback guidance" in sql
