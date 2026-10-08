from datetime import datetime
from pathlib import Path

from src.pipeline.date_utils import VN_TZ
from src.pipeline.workflow_dates import resolve_workflow_date


def test_stock_eod_workflow_uses_renamed_stock_only_command():
    text = Path(".github/workflows/stock-eod.yml").read_text()
    assert "name: TradingTPlus Stock EOD Pipeline" in text
    assert 'cron: "30 9 * * 1-5"' in text
    assert '      timezone: "Asia/Ho_Chi_Minh"' not in text
    assert "  stock-eod:" in text
    assert "tradingtplus-stock-eod-" in text
    assert 'cmd=(python main.py stock-eod "$TARGET_DATE")' in text
    assert "src.pipeline.workflow_dates stock-eod" in text
    assert "python main.py eod" not in text
    assert "data_source:" in text
    assert '!= "auto"' in text
    assert not Path(".github/workflows/eod.yml").exists()


def test_index_eod_remains_independent():
    text = Path(".github/workflows/index-eod.yml").read_text()
    assert "python main.py index-daily" in text
    assert 'cron: "30 1 * * 2-6"' in text
    assert '      timezone: "Asia/Ho_Chi_Minh"' not in text
    assert "src.pipeline.workflow_dates index" in text
    assert 'cmd=(python main.py index-daily "$TARGET_DATE")' in text
    for forbidden_command in (
        "python main.py stock-eod",
        "python main.py stock-intraday",
        "python main.py features",
        "python main.py signals",
        "python main.py backtest",
    ):
        assert forbidden_command not in text


def test_delayed_stock_schedule_uses_intended_vietnam_slot_date():
    delayed_runtime = datetime(2026, 10, 6, 1, 46, tzinfo=VN_TZ)
    result = resolve_workflow_date("stock", "schedule", now=delayed_runtime)
    assert result.target_date == "05/10/2026"
    assert result.target_source == "scheduled"


def test_stock_manual_date_and_inputs_remain_supported():
    result = resolve_workflow_date(
        "stock",
        "workflow_dispatch",
        "05/10/2026",
        now=datetime(2026, 10, 6, 1, 46, tzinfo=VN_TZ),
    )
    assert result.target_date == "05/10/2026"
    assert result.target_source == "manual"
    text = Path(".github/workflows/stock-eod.yml").read_text()
    assert 'read -r -a symbols <<< "$SYMBOLS_INPUT"' in text
    assert 'cmd+=(--data-source "$DATA_SOURCE_INPUT")' in text


def test_index_tuesday_schedule_targets_monday_and_manual_date_wins():
    tuesday_morning = datetime(2026, 10, 6, 8, 40, tzinfo=VN_TZ)
    scheduled = resolve_workflow_date("index", "schedule", now=tuesday_morning)
    manual = resolve_workflow_date(
        "index", "workflow_dispatch", "02/10/2026", now=tuesday_morning
    )
    assert scheduled.target_date == "05/10/2026"
    assert scheduled.target_source == "scheduled"
    assert manual.target_date == "02/10/2026"
    assert manual.target_source == "manual"

    iso_manual = resolve_workflow_date(
        "index", "workflow_dispatch", "2026-10-02", now=tuesday_morning
    )
    assert iso_manual.target_date == "2026-10-02"


def test_workflows_log_timing_resolution_context():
    for workflow in ("stock-eod.yml", "stock-intraday.yml", "index-eod.yml"):
        text = Path(".github/workflows", workflow).read_text()
        assert 'echo "event=${{ github.event_name }}"' in text
        assert 'echo "runtime_vn=${{ steps.resolve-date.outputs.runtime_vn }}"' in text
        assert 'echo "scheduled_slot_vn=${{ steps.resolve-date.outputs.scheduled_slot_vn }}"' in text
        assert 'echo "target_date=$TARGET_DATE"' in text
        assert 'echo "target_source=${{ steps.resolve-date.outputs.target_source }}"' in text
