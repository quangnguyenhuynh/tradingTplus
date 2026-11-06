"""Workflow-only EOD scheduling; never contacts SSI or Supabase."""
from datetime import datetime
from pathlib import Path
import textwrap

import pytest

WORKFLOWS = Path(".github/workflows")
STOCK = WORKFLOWS / "stock-eod-scheduled.yml"
INDEX = WORKFLOWS / "index-eod-scheduled.yml"


def test_old_eod_workflows_retired_and_new_crons_correct():
    assert not (WORKFLOWS / "stock-eod.yml").exists()
    assert not (WORKFLOWS / "index-eod-v2.yml").exists()
    stock, index = STOCK.read_text(), INDEX.read_text()
    assert 'cron: "7 10 * * 1-5"' in stock   # 17:07 Vietnam, Mon-Fri
    assert 'cron: "7 1 * * 2-6"' in index    # 08:07 Vietnam, Tue-Sat
    assert 'cmd=(python main.py stock-eod)' in stock
    assert 'cmd=(python main.py index-eod)' in index
    assert 'cmd+=("$TARGET_DATE")' in stock
    assert 'cmd+=("$TARGET_DATE")' in index
    assert 'if [ -n "$TARGET_DATE" ]; then' in stock
    assert 'if [ -n "$TARGET_DATE" ]; then' in index
    assert "src.ingest.workflows.workflow_dates" not in stock + index
    assert "features-daily" not in stock + index
    assert 'read -r -a symbols <<< "$SYMBOLS_INPUT"' in stock
    assert 'read -r -a indexes <<< "$INDEXES_INPUT"' in index
    assert 'cmd+=(--data-source "$DATA_SOURCE_INPUT")' in stock


def _run_date_resolver(path, now_iso, event, manual, monkeypatch, capsys):
    """Run the exact inline workflow Python under a deterministic local clock."""
    yaml = path.read_text()
    script = yaml.split("python - <<'PY' | tee -a \"$GITHUB_OUTPUT\"", 1)[1].split("\n          PY", 1)[0]
    code = textwrap.dedent(script)
    assert 'datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))' in code
    code = code.replace(
        'datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))',
        'datetime.fromisoformat(' + repr(now_iso) + ').replace(tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))',
    )
    monkeypatch.setenv("RUN_EVENT", event)
    monkeypatch.setenv("DATE_INPUT", manual)
    exec(compile(code, str(path), "exec"), {"__name__": "__main__"})
    return dict(line.split("=", 1) for line in capsys.readouterr().out.splitlines())


@pytest.mark.parametrize("path,now,target", [
    (STOCK, "2026-11-05T17:07", "05/11/2026"),
    (STOCK, "2026-11-06T18:30", "06/11/2026"),
    (INDEX, "2026-11-06T08:07", "05/11/2026"),
    (INDEX, "2026-11-07T08:10", "06/11/2026"),
    (INDEX, "2026-11-10T09:00", "09/11/2026"),
])
def test_schedule_targets_intended_session(path, now, target, monkeypatch, capsys):
    result = _run_date_resolver(path, now, "schedule", "", monkeypatch, capsys)
    assert result["target_date"] == target
    assert result["target_source"].startswith("scheduled_")


@pytest.mark.parametrize("path,now", [
    (STOCK, "2026-11-06T02:00"),  # next-day execution must not select today
    (STOCK, "2026-11-06T22:00"),  # too-late job
    (INDEX, "2026-11-06T07:30"),  # early, before intended slot
    (INDEX, "2026-11-09T08:10"),  # Monday is not a configured Index slot
    (INDEX, "2026-11-07T13:00"),  # too-late job
])
def test_delayed_or_invalid_schedule_blocks(path, now, monkeypatch, capsys):
    with pytest.raises(SystemExit):
        _run_date_resolver(path, now, "schedule", "", monkeypatch, capsys)


@pytest.mark.parametrize("path", [STOCK, INDEX])
@pytest.mark.parametrize("date,source", [("", "cli_default"), ("05/11/2026", "manual"), ("2026-11-05", "manual")])
def test_manual_date_or_original_cli_default(path, date, source, monkeypatch, capsys):
    result = _run_date_resolver(path, "2026-11-06T02:00", "workflow_dispatch", date, monkeypatch, capsys)
    assert result["target_date"] == date
    assert result["target_source"] == source
