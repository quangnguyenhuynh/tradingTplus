from pathlib import Path


SQL = (Path(__file__).parents[2] / "migrations" / "20260827_add_master_status.sql").read_text().lower()


def test_master_status_migration_is_additive_and_constrained():
    assert "alter table public.symbols" in SQL
    assert "alter table public.index_master" in SQL
    assert SQL.count("add column if not exists status text") == 2
    assert "symbols_status_check" in SQL
    assert "index_master_status_check" in SQL
    assert "check (status in ('active', 'inactive'))" in SQL
    assert SQL.count("set status = 'active'") == 2
    assert "drop table" not in SQL
    assert "truncate" not in SQL

INTRADAY_SQL = (Path(__file__).parents[2] / "migrations" / "20260829_add_symbols_intraday_status.sql").read_text().lower()


def test_intraday_status_migration_is_additive_safe_and_constrained():
    assert "add column if not exists intraday_status text" in INTRADAY_SQL
    assert "set intraday_status = status" in INTRADAY_SQL
    assert "alter column intraday_status set default 'inactive'" in INTRADAY_SQL
    assert "alter column intraday_status set not null" in INTRADAY_SQL
    assert "symbols_intraday_status_check" in INTRADAY_SQL
    assert "check (intraday_status in ('active', 'inactive'))" in INTRADAY_SQL
    for forbidden in ("drop table", "truncate", "delete from"):
        assert forbidden not in INTRADAY_SQL
