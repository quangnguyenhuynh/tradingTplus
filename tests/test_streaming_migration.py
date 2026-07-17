from pathlib import Path


def test_streaming_reconciliation_migration_is_additive_and_idempotent():
    sql = Path("migrations/20260717_reconcile_streaming_ingest.sql").read_text().lower()
    assert "create table if not exists" in sql
    assert "add column if not exists" in sql
    assert "create unique index if not exists" in sql
    executable_sql = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    for forbidden in ["drop table", "drop column", "truncate", "delete from"]:
        assert forbidden not in executable_sql
    assert "stream_status_snapshot" in sql
    assert "stream_bar_snapshot" in sql
    assert "ux_stream_raw_snapshot_payload_hash" in sql
