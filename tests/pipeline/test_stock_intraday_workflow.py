from pathlib import Path


def test_intraday_has_no_schedule_credentials_or_service_calls():
    text = Path(".github/workflows/stock-intraday.yml").read_text()
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text and "cron:" not in text
    assert "secrets." not in text and "main.py stock-intraday" not in text
    assert "NOT_IMPLEMENTED" in text and "exit 1" in text
