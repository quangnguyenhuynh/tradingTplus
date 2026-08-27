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
