from pathlib import Path


def test_stock_intraday_workflow_is_independent_and_scheduled():
    intraday = Path(".github/workflows/stock-intraday.yml").read_text()
    eod = Path(".github/workflows/stock-eod.yml").read_text()
    assert 'cron: "0 10 * * 1-5"' in intraday
    assert '      timezone: "Asia/Ho_Chi_Minh"' not in intraday
    assert 'cmd=(python main.py stock-intraday "$TARGET_DATE")' in intraday
    assert "src.pipeline.workflow_dates stock-intraday" in intraday
    assert 'TARGET_DATE: ${{ steps.resolve-date.outputs.target_date }}' in intraday
    assert '--manual-date "$DATE_INPUT"' in intraday
    assert 'read -r -a symbols <<< "$SYMBOLS_INPUT"' in intraday
    assert "workflow_dispatch:" in intraday and "date:" in intraday and "symbols:" in intraday
    assert "cancel-in-progress: false" in intraday
    assert "tradingtplus-stock-intraday-" in intraday
    assert "tradingtplus-stock-eod-" in eod
    assert "tradingtplus-stock-intraday-" not in eod
