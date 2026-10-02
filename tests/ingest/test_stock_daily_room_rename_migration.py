from pathlib import Path

from scripts.check_ssi_ingest_schema import REQUIRED_COLUMNS


MIGRATION = Path(
    "migrations/20261002_rename_stock_daily_foreign_remaining_room.sql"
)


def test_stock_daily_room_rename_migration_guards_all_existing_states():
    sql = MIGRATION.read_text().lower()

    assert "column_name = 'foreign_current_room'" in sql
    assert "column_name = 'foreign_remaining_room'" in sql
    assert "if old_column_exists and new_column_exists then" in sql
    assert "raise exception" in sql
    assert "elsif old_column_exists and not new_column_exists then" in sql
    assert "rename column foreign_current_room to foreign_remaining_room" in sql
    assert "notify pgrst, 'reload schema'" in sql


def test_stock_daily_schema_checker_expects_only_canonical_room_name():
    columns = REQUIRED_COLUMNS["stock_daily"]

    assert "foreign_remaining_room" in columns
    assert "foreign_total_room" in columns
    assert "foreign_current_room" not in columns

    schema = Path("schema.sql").read_text().lower()
    assert "foreign_remaining_room numeric" in schema
    assert "foreign_current_room" not in schema
