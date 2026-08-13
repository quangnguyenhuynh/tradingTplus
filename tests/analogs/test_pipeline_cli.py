from datetime import date, timedelta
import pytest
import main
from src.analogs.pipeline import build_history, daily_run
from src.analogs.profile import load_profile


class Repo:
    def __init__(self):
        self.snapshots = []
        self.deleted = 0

    def upsert_snapshots(self, rows):
        self.snapshots = list(rows)
        return len(self.snapshots)

    def replace_scope(self, **kwargs):
        self.deleted += 1
        return 2


def rows():
    sessions = [date(2026, 1, 1) + timedelta(days=i) for i in range(12)]
    features = []
    for symbol in ("SSI", "HPG"):
        for i, session in enumerate(sessions):
            features.append(
                {
                    "symbol": symbol,
                    "timeframe": "1d",
                    "trading_session": session,
                    "close": 100 + i,
                    "low": 99 + i,
                    "high": 102 + i,
                    "ema20": 90 + i,
                    "ema50": 80 + i,
                    "rsi14": 50 + i,
                    "macd_histogram": 1,
                    "high_20_bars": 110 + i,
                    "volume_ratio": 1 + i / 10,
                    "value_ratio": 1 + i / 20,
                }
            )
    closes = {(row["symbol"], row["trading_session"]): row["close"] for row in features}
    return sessions, features, closes


def test_full_incremental_replace_scoped_and_idempotent():
    p = load_profile()
    sessions, features, closes = rows()
    repo = Repo()
    kwargs = dict(
        profile=p,
        feature_rows=features,
        sessions=sessions,
        closes=closes,
        symbols=["ssi"],
        start=sessions[5],
        end=sessions[7],
        repository=repo,
    )
    first = build_history(**kwargs, mode="full", apply=True)
    second = build_history(**kwargs, mode="incremental", apply=True)
    assert first["snapshot_count"] == 3 and second["snapshot_count"] == 8 and {
        r["symbol"] for r in repo.snapshots
    } == {"SSI"}
    with pytest.raises(ValueError, match="confirm"):
        build_history(**kwargs, mode="replace", apply=True)
    replaced = build_history(**kwargs, mode="replace", apply=True, confirm_replace=True)
    assert replaced["deleted_count"] == 2
    with pytest.raises(ValueError, match="explicit symbol"):
        build_history(**{**kwargs, "symbols": []}, mode="full")


def test_daily_requires_scope_and_blocks_draft():
    p = load_profile()
    row = {
        "profile_code": p.code,
        "version": 1,
        "config_hash": p.config_hash,
        "status": "draft",
        "configuration": p.config,
    }
    with pytest.raises(ValueError):
        daily_run(row, symbols=[], session=date.today())
    assert daily_run(row, symbols=["ssi"], session=date.today())["reason_codes"] == [
        "EXACT_PROFILE_NOT_APPROVED",
        "DISTANCE_THRESHOLD_NULL",
    ]


def test_cli_dry_run_apply_and_production_rejection(capsys):
    assert main.main(["analogs", "profiles", "register"]) == 0
    assert '"dry_run": true' in capsys.readouterr().out
    args = [
        "analogs",
        "history",
        "build",
        "--profile",
        "TPLUS_ANALOG_CORE_EOD",
        "--version",
        "1",
        "--config-hash",
        "a" * 64,
        "--symbols",
        "ssi",
        "--from",
        "01/01/2026",
        "--to",
        "02/01/2026",
        "--mode",
        "full",
    ]
    assert main.main(args) == 2
    assert "SOURCE_PROFILE_CONFIG_HASH_MISMATCH" in capsys.readouterr().err
    query = [
        "analogs",
        "query",
        "--profile",
        "TPLUS_ANALOG_CORE_EOD",
        "--version",
        "1",
        "--symbol",
        "SSI",
        "--date",
        "02/01/2026",
    ]
    assert main.main(query) == 0
    output = capsys.readouterr().out
    assert (
        "DISTANCE_THRESHOLD_NULL" in output and "EXACT_PROFILE_NOT_APPROVED" in output
    )


def test_cli_can_select_v2_registration_and_blocks_v2_production(capsys):
    selected = [
        "analogs", "profiles", "register", "--profile",
        "TPLUS_ANALOG_CORE_EOD", "--version", "2",
    ]
    assert main.main(selected) == 0
    assert '"version": 2' in capsys.readouterr().out
    query = [
        "analogs", "query", "--profile", "TPLUS_ANALOG_CORE_EOD",
        "--version", "2", "--symbol", "SSI", "--date", "02/01/2026",
    ]
    assert main.main(query) == 0
    output = capsys.readouterr().out
    assert "EXACT_PROFILE_NOT_APPROVED" in output
    assert "DISTANCE_THRESHOLD_NULL" in output
