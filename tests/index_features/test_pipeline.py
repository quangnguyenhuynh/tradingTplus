from types import SimpleNamespace

import pandas as pd

from src.index_features import pipeline
from src.index_features import completeness
from src.index_features.repository import frame_to_records


def rows(count=70):
    result = []
    for i, date in enumerate(pd.bdate_range("2026-01-01", periods=count)):
        result.append({"index_code": "VNINDEX", "trading_date": date.date().isoformat(),
            "index_value": 100+i, "total_vol": 1000+i, "total_val": 10000+i,
            "total_match_vol": 800+i, "total_match_val": 8000+i,
            "total_deal_vol": 200, "total_deal_val": 2000, "advances": 60,
            "no_changes": 10, "declines": 30, "ceilings": 5, "floors": 2})
    return result


def setup(monkeypatch, writes):
    monkeypatch.setattr(pipeline, "resolve_index_scope", lambda db, indexes: (["VNINDEX"], indexes))
    monkeypatch.setattr(pipeline, "fetch_index_daily_context", lambda db, code, start, end: rows())
    monkeypatch.setattr(pipeline, "upsert_index_features", lambda db, records: writes.extend(records))


def test_preview_is_read_only_and_reads_clean_context_only(monkeypatch):
    writes = []; setup(monkeypatch, writes)
    summary = pipeline.run_index_features_preview("08/04/2026", ["VNINDEX"], db=object())
    assert summary["mode"] == "preview" and summary["feature_row_count"] == 1
    assert writes == []
    assert summary["rows"][0]["trading_date"] == "2026-04-08"


def test_backfill_writes_only_requested_dates_and_is_rerunnable(monkeypatch):
    writes = []; setup(monkeypatch, writes)
    first = pipeline.run_index_features_backfill("01/04/2026", "09/04/2026", ["VNINDEX"], db=object())
    assert writes and all("2026-04-01" <= row["trading_date"] <= "2026-04-09" for row in writes)
    count = len(writes); writes.clear()
    second = pipeline.run_index_features_backfill("01/04/2026", "09/04/2026", ["VNINDEX"], db=object())
    assert len(writes) == count == first["feature_row_count"] == second["feature_row_count"]


def test_missing_clean_rows_create_no_features(monkeypatch):
    writes = []
    monkeypatch.setattr(pipeline, "resolve_index_scope", lambda db, indexes: (["HNX30"], indexes))
    monkeypatch.setattr(pipeline, "fetch_index_daily_context", lambda *args: [])
    monkeypatch.setattr(pipeline, "upsert_index_features", lambda db, records: writes.extend(records))
    summary = pipeline.run_index_features_daily("25/08/2026", ["HNX30"], db=object())
    assert summary["source_rows"] == {"HNX30": 0}
    assert summary["feature_row_count"] == 0 and writes == []


def test_record_sanitization_supplies_non_null_audit_timestamps():
    frame = pd.DataFrame([{"index_code": "VNINDEX", "trading_date": pd.Timestamp("2026-01-01"), "index_value": float("nan")}])
    record = frame_to_records(frame)[0]
    assert record["index_value"] is None
    assert record["created_at"] is not None and record["updated_at"] is not None


def test_completeness_reports_raw_without_clean_and_insufficient_history(monkeypatch):
    monkeypatch.setattr(completeness, "resolve_index_scope", lambda db, indexes: (["HNX30"], indexes))
    monkeypatch.setattr(completeness, "_prior_clean_count", lambda db, code, start: 0)
    def fake_rows(db, table, columns, code, start, end):
        return [{"index_code": code, "trading_date": "2026-08-25"}] if table == "index_raw_daily" else []
    monkeypatch.setattr(completeness, "_rows", fake_rows)
    summary = completeness.check_index_features("25/08/2026", "25/08/2026", ["HNX30"], db=object())
    detail = summary["indexes_detail"][0]
    assert detail["raw_without_clean"] == ["2026-08-25"]
    assert detail["clean_source_row_count"] == detail["expected_feature_row_count"] == 0
    assert detail["insufficient_history"] is True
