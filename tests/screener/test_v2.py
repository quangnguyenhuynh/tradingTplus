import pytest

import main
from src.screener.config import load_v2, describe_config, _validate
from src.screener.rules_v2 import evaluate_v2
from src.screener.rules import evaluate


def _base():
    return dict(close=110, ema20=100, ema50=95, rsi14=60,
                macd_histogram=1, volume_ratio=1.2, value_ratio=1.2)


def test_methodology_config_is_valid_and_deterministic():
    a, b = load_v2(), load_v2()
    assert a["config_hash"] == b["config_hash"]
    assert len(a["config_hash"]) == 64
    assert "40" in a["methodology_vi_md"]
    assert "40" in a["methodology_md"]


def test_v2_can_pass_without_all_five_gates():
    profile = load_v2()
    out = evaluate_v2({**_base(), "value_ratio": 0.7}, profile["config"])
    assert out["status"] == "PASS"
    assert out["score"] == 85
    assert out["rule_results"]["weighted_rules"]["value"]["earned"] == 0
    assert evaluate({**_base(), "value_ratio": 0.7})["status"] == "FAIL"


def test_v2_missing_is_null_and_not_evaluable():
    result = evaluate_v2({**_base(), "rsi14": None}, load_v2()["config"])
    assert result["score"] is None
    assert result["status"] == "NOT_EVALUABLE"
    assert result["rule_results"]["weighted_rules"]["rsi"]["earned"] is None


def test_config_validation_rejects_weight_drift():
    config = load_v2()["config"]
    config["rules"][0]["weight"] = 39
    with pytest.raises(ValueError, match="sum to 100"):
        _validate(config)


def test_config_preview_is_read_only():
    output = describe_config()
    assert output["mode"] == "preview"
    assert output["screener_version"] == "v2"


def test_v2_cli_routes_and_preserves_v1_signature(monkeypatch):
    args = []
    monkeypatch.setattr(main, "run_stock_screener", lambda *a, **kw: args.append((a, kw)) or {"status": "OK"})
    assert main.main(["stock-screener", "--date", "13/08/2026", "--symbols", "SSI"]) == 0
    assert "version" not in args[-1][1]
    assert main.main(["stock-screener", "--date", "13/08/2026", "--symbols", "SSI", "--version", "v2"]) == 0
    assert args[-1][1]["version"] == "v2"


def test_config_cli_preview(monkeypatch):
    monkeypatch.setattr(main, "describe_config", lambda *a, **kw: {"status": "OK"})
    assert main.main(["stock-screener-config", "--version", "v2"]) == 0
