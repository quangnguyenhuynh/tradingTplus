from pathlib import Path


SQL = Path("migrations/20260826_add_index_daily_primary_key.sql").read_text()
NORMALIZED_SQL = " ".join(SQL.lower().split())


def test_migration_preflights_null_and_duplicate_business_keys():
    assert "where index_code is null or trading_date is null" in NORMALIZED_SQL
    assert "group by index_code, trading_date having count(*) > 1" in NORMALIZED_SQL
    assert "raise exception 'cannot add index_daily_pkey:" in NORMALIZED_SQL


def test_migration_reuses_unique_index_for_ordered_composite_primary_key():
    assert "alter column index_code set not null" in NORMALIZED_SQL
    assert "alter column trading_date set not null" in NORMALIZED_SQL
    assert (
        "add constraint index_daily_pkey primary key using index "
        "index_daily_index_code_trading_date_uidx"
    ) in NORMALIZED_SQL
    assert "create unique index" not in NORMALIZED_SQL.split("commit;", 1)[0]


def test_migration_is_transactional_and_does_not_mutate_row_values():
    assert NORMALIZED_SQL.startswith("-- promote")
    assert "begin;" in NORMALIZED_SQL
    assert "commit;" in NORMALIZED_SQL
    migration_body = NORMALIZED_SQL.split("commit;", 1)[0]
    for forbidden in ("delete from", "truncate", "update public.index_daily", "drop table"):
        assert forbidden not in migration_body
