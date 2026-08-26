import ast
import re
from pathlib import Path


ORIGINAL = Path("migrations/20260826_standardize_stock_table_names.sql")
CORRECTIVE = Path("migrations/20260827_restore_domain_table_names.sql")
VERIFY = Path("sql/verify_restore_domain_table_names.sql")
RETAINED = {
    "stock_raw_daily", "stock_raw_intraday", "stock_features",
    "stock_foreign_trading", "stock_orderbook_snapshot", "stock_data_quality_logs",
}
RESTORED = {
    "stock_symbols": "symbols", "stock_securities": "securities",
    "stock_analog_profiles": "analog_profiles", "stock_analog_snapshots": "analog_snapshots",
    "stock_analog_outcomes": "analog_outcomes", "stock_analog_queries": "analog_queries",
    "stock_analog_query_matches": "analog_query_matches",
    "stock_analog_validation_runs": "analog_validation_runs",
    "stock_analog_profile_reviews": "analog_profile_reviews",
    "stock_stream_quote_snapshot": "stream_quote_snapshot",
    "stock_stream_trade_snapshot": "stream_trade_snapshot",
    "stock_stream_foreign_snapshot": "stream_foreign_snapshot",
    "stock_stream_status_snapshot": "stream_status_snapshot",
    "stock_stream_bar_snapshot": "stream_bar_snapshot",
}
UNCHANGED = {
    "stock_daily", "stock_intraday", "stream_raw_snapshot", "stream_index_snapshot",
    "index_master", "index_components", "index_raw_daily", "index_daily", "index_features_daily",
}


def sql(path: Path) -> str:
    return path.read_text().lower()


def mapping_block() -> str:
    body = sql(CORRECTIVE)
    return body.split("insert into domain_table_restore_map", 1)[1].split("do $restore_tables$", 1)[0]


def function_body(body: str, name: str) -> str:
    return body.split(f"function public.{name}", 1)[1].split("end $$;", 1)[0]


def test_historical_migration_is_preserved_and_corrective_restores_exactly_fourteen():
    historical = sql(ORIGINAL)
    block = mapping_block()
    assert all(f"('{old}','{new}')" in historical for new, old in RESTORED.items())
    assert set(re.findall(r"\('([a-z_]+)','([a-z_]+)'\)", block)) == set(RESTORED.items())
    assert len(RESTORED) == 14


def test_corrective_is_atomic_bounded_restart_safe_and_explicit_on_invalid_states():
    body = sql(CORRECTIVE)
    assert body.startswith("-- correct") and "begin;" in body and "commit;" in body
    assert "set local lock_timeout = '5s'" in body
    assert "set local statement_timeout = '2min'" in body
    assert "incorrect_oid is not null and correct_oid is not null" in body
    assert "incorrect_oid is null and correct_oid is null" in body
    assert "elsif incorrect_oid is not null then" in body  # final-only is a no-op
    assert "ambiguous domain table restore" in body
    assert "missing domain schema" in body
    assert "alter table public.%i rename to %i" in body
    assert "notify pgrst, 'reload schema';" in body


def test_corrective_never_recreates_copies_or_removes_table_data():
    body = sql(CORRECTIVE)
    executable = body.split("-- run sql/verify", 1)[0]
    for forbidden in ("drop table", "truncate", "create table as", "select * into", "delete from"):
        assert forbidden not in executable
    assert "create table public." not in executable
    assert executable.count("alter table public.%i rename to %i") == 1


def test_retained_stock_and_unchanged_domain_tables_are_not_in_restore_mapping():
    block = mapping_block()
    for table in RETAINED | UNCHANGED:
        assert table not in block
    assert "stock_intraday_" not in block


def test_function_contracts_are_correct_after_sequential_migrations():
    historical = sql(ORIGINAL)
    corrective = sql(CORRECTIVE)
    persist = function_body(corrective, "persist_analog_query_v1")
    assert "returns setof public.analog_queries" in persist
    assert "declare v_query public.analog_queries" in persist
    assert "insert into public.analog_queries" in persist
    assert "insert into public.analog_query_matches" in persist
    assert "security definer set search_path=''" in persist
    assert "revoke" not in persist and "grant" not in persist
    assert "public.stock_analog_" not in persist
    assert "delete from public.stock_orderbook_snapshot" in historical
    assert "delete from public.stock_raw_intraday" in historical
    assert "delete from public.stock_features" in historical
    assert "null::public.stock_features" in historical


def test_catalog_normalization_is_scoped_collision_safe_and_verifiable():
    body = sql(CORRECTIVE)
    assert "domain_object_tables" in body
    assert all(f"('{name}','{name}')" in body for name in RETAINED)
    assert "constraint rename collision" in body
    assert "index rename collision" in body
    assert "sequence rename collision" in body
    assert "alter table public.%i rename constraint" in body
    assert "alter index public.%i rename" in body
    assert "alter sequence public.%i rename" in body
    verification = sql(VERIFY)
    assert "not convalidated" in verification
    assert "stock\\_stock\\_%" in verification


def test_verification_covers_fks_partitions_rls_policies_functions_and_counts():
    body = sql(VERIFY)
    for token in ("pg_inherits", "confrelid", "convalidated", "relrowsecurity",
                  "pg_policies", "pg_get_functiondef", "row_count"):
        assert token in body
    for table in RETAINED | set(RESTORED.values()) | UNCHANGED:
        assert f"'{table}'" in body
    for table in RESTORED:
        assert f"'{table}'" in body


def test_schema_snapshot_has_final_contract_and_no_incorrect_relations():
    schema = sql(Path("schema.sql"))
    inventory = schema.split("-- post-20260826 stock-domain relation inventory", 1)[1].split(
        "create table", 1
    )[0]
    for table in RETAINED | set(RESTORED.values()) | UNCHANGED:
        assert (
            re.search(rf'create table if not exists "public"\."{table}"', schema)
            or re.search(rf"\b{table}\b", inventory)
        )
    for table in RESTORED:
        assert not re.search(rf'create table if not exists "public"\."{table}"', schema)


def test_application_supabase_calls_use_final_contract():
    forbidden = set(RESTORED) | {"raw_daily", "raw_intraday", "features", "foreign_trading",
                                "orderbook_snapshot", "data_quality_logs"}
    for root in (Path("src"), Path("scripts")):
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "table":
                    if node.args and isinstance(node.args[0], ast.Constant):
                        assert node.args[0].value not in forbidden, f"{path}: {node.args[0].value}"
