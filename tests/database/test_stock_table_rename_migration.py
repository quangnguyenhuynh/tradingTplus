import ast
import re
from pathlib import Path


MIGRATION = Path("migrations/20260826_standardize_stock_table_names.sql")
MAPPING = {
    "raw_daily": "stock_raw_daily",
    "raw_intraday": "stock_raw_intraday",
    "features": "stock_features",
    "foreign_trading": "stock_foreign_trading",
    "orderbook_snapshot": "stock_orderbook_snapshot",
    "data_quality_logs": "stock_data_quality_logs",
}
EXCLUDED = {
    "stock_daily", "stock_intraday", "symbols", "securities",
    "analog_profiles", "analog_snapshots", "analog_outcomes", "analog_queries",
    "analog_query_matches", "analog_validation_runs", "analog_profile_reviews",
    "stream_raw_snapshot", "stream_quote_snapshot", "stream_trade_snapshot",
    "stream_foreign_snapshot", "stream_index_snapshot", "stream_status_snapshot",
    "stream_bar_snapshot", "index_master", "index_components", "index_raw_daily",
    "index_daily", "index_features_daily",
}


def text() -> str:
    return MIGRATION.read_text()


def mapping_block() -> str:
    sql = text().lower()
    return sql.split("insert into stock_table_rename_map", 1)[1].split("do $migration$", 1)[0]


def test_exactly_six_metadata_only_mappings_are_atomic_and_restart_safe():
    sql = text().lower()
    block = mapping_block()
    assert sql.startswith("-- standardize") and "begin;" in sql and "commit;" in sql
    assert "set local lock_timeout" in sql
    assert set(re.findall(r"\('([a-z_]+)','([a-z_]+)'\)", block)) == set(MAPPING.items())
    assert "both public.% and public.% exist" in sql
    assert "neither public.% nor public.% exists" in sql
    assert "alter table public.%i rename to %i" in sql
    assert "notify pgrst, 'reload schema';" in sql


def test_migration_never_recreates_copies_or_removes_table_data():
    sql = text().lower()
    for forbidden in ("drop table", "truncate", "create table as", "select * into"):
        assert forbidden not in sql
    for old, new in MAPPING.items():
        assert not re.search(rf"insert\s+into\s+(?:public\.)?{new}\b[\s\S]*?from\s+(?:public\.)?{old}\b", sql)


def test_only_three_affected_functions_use_post_rename_contract():
    sql = text().lower()
    functions = re.findall(r"create or replace function public\.([a-z_]+)", sql)
    assert functions == ["cleanup_old_orderbook", "cleanup_old_raw_data", "replace_features_atomic"]
    assert "delete from public.stock_orderbook_snapshot" in sql
    assert "delete from public.stock_raw_intraday" in sql
    assert "delete from public.stock_features" in sql
    assert "null::public.stock_features" in sql
    assert "persist_analog_query_v1" not in sql


def test_excluded_tables_are_not_renamed():
    block = mapping_block()
    for table in EXCLUDED:
        assert not re.search(rf"\('{table}','|,'{table}'\)", block)
    for forbidden_prefix in ("stock_analog_", "stock_stream_", "stock_symbols", "stock_securities"):
        assert forbidden_prefix not in block


def test_stock_features_is_still_one_unified_table_with_unchanged_key_and_columns():
    schema = Path("schema.sql").read_text()
    block = schema.split('CREATE TABLE IF NOT EXISTS "public"."stock_features"', 1)[1].split(");", 1)[0]
    for column in ('"symbol"', '"timeframe"', '"time"', '"open"', '"high"', '"low"', '"close"', '"volume"', '"value"'):
        assert column in block
    assert 'ADD CONSTRAINT "stock_features_pkey" PRIMARY KEY ("symbol", "timeframe", "time")' in schema


def test_executable_supabase_table_calls_do_not_use_legacy_names():
    for root in (Path("src"), Path("scripts")):
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "table":
                    if node.args and isinstance(node.args[0], ast.Constant):
                        assert node.args[0].value not in MAPPING, f"{path}: legacy table call {node.args[0].value}"


def test_schema_snapshot_and_current_sql_do_not_reference_legacy_relations():
    relation = re.compile(r"\b(?:from|into|update|table|references|join)\s+(?:public\.)?([a-z_]+)", re.I)
    for path in [Path("schema.sql"), *Path("sql").rglob("*.sql")]:
        for name in relation.findall(path.read_text()):
            assert name.lower() not in MAPPING, f"{path}: legacy relation {name}"
