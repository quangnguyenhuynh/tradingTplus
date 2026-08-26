import ast
import re
from pathlib import Path


MIGRATION = Path("migrations/20260826_standardize_stock_table_names.sql")
MAPPING = {
    "symbols": "stock_symbols", "securities": "stock_securities",
    "raw_daily": "stock_raw_daily", "raw_intraday": "stock_raw_intraday",
    "features": "stock_features", "foreign_trading": "stock_foreign_trading",
    "orderbook_snapshot": "stock_orderbook_snapshot", "data_quality_logs": "stock_data_quality_logs",
    "analog_profiles": "stock_analog_profiles", "analog_snapshots": "stock_analog_snapshots",
    "analog_outcomes": "stock_analog_outcomes", "analog_queries": "stock_analog_queries",
    "analog_query_matches": "stock_analog_query_matches", "analog_validation_runs": "stock_analog_validation_runs",
    "analog_profile_reviews": "stock_analog_profile_reviews",
    "stream_quote_snapshot": "stock_stream_quote_snapshot", "stream_trade_snapshot": "stock_stream_trade_snapshot",
    "stream_foreign_snapshot": "stock_stream_foreign_snapshot", "stream_status_snapshot": "stock_stream_status_snapshot",
    "stream_bar_snapshot": "stock_stream_bar_snapshot",
}


def text() -> str:
    return MIGRATION.read_text()


def test_all_twenty_metadata_only_mappings_are_atomic_and_restart_safe():
    sql = text().lower()
    assert sql.startswith("-- standardize") and "begin;" in sql and "commit;" in sql
    assert "set local lock_timeout" in sql
    for old, new in MAPPING.items():
        assert f"('{old}','{new}')" in sql
    assert "both public.% and public.% exist" in sql
    assert "neither public.% nor public.% exists" in sql
    assert "alter table public.%i rename to %i" in sql
    assert "notify pgrst, 'reload schema';" in sql


def test_migration_never_recreates_or_copies_stock_data():
    sql = text().lower()
    assert "drop table" not in sql
    assert "truncate" not in sql
    assert "create table as" not in sql
    assert "select * into" not in sql
    for old, new in MAPPING.items():
        assert not re.search(
            rf"insert\s+into\s+public\.{new}\b[\s\S]*?select[\s\S]*?from\s+public\.{old}\b",
            sql,
        )


def test_functions_rls_foreign_keys_and_partitions_use_post_rename_contract():
    sql = text().lower()
    for function in ("cleanup_old_orderbook", "cleanup_old_raw_data", "persist_analog_query_v1", "replace_features_atomic"):
        assert f"create or replace function public.{function}" in sql
    assert "returns setof public.stock_analog_queries" in sql
    assert "public.stock_analog_query_matches" in sql
    assert "from public.stock_analog_queries q" in sql
    assert "to authenticated" in sql and "to service_role" in sql
    assert "confrelid='public.stock_symbols'::regclass" in sql
    assert "inhparent='public.stock_intraday'::regclass" in sql


def test_excluded_domain_tables_are_not_mapped():
    assert not (set(MAPPING) | set(MAPPING.values())) & {
        "stock_daily", "stock_intraday", "index_master", "index_raw_daily",
        "index_daily", "index_features_daily", "index_components",
        "stream_index_snapshot", "stream_raw_snapshot",
    }
    sql = text()
    assert "stream_raw_snapshot" in sql and "stream_index_snapshot" in sql


def test_executable_supabase_table_calls_do_not_use_legacy_names():
    legacy = set(MAPPING)
    for root in (Path("src"), Path("scripts")):
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                if node.func.attr == "table" and node.args and isinstance(node.args[0], ast.Constant):
                    assert node.args[0].value not in legacy, f"{path}: legacy table call {node.args[0].value}"


def test_schema_snapshot_and_current_sql_do_not_reference_legacy_relations():
    paths = [Path("schema.sql"), *Path("sql").rglob("*.sql")]
    relation = re.compile(r"\b(?:from|into|update|table|references|join)\s+(?:public\.)?([a-z_]+)", re.I)
    for path in paths:
        for name in relation.findall(path.read_text()):
            assert name.lower() not in MAPPING, f"{path}: legacy relation {name}"
