"""Source-controlled executable config and human methodology for Screener V2."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from src.database.client import SupabaseClient
from src.utils.time_utils import app_now_iso

_ROOT = Path(__file__).resolve().parent
_RULE_IDS = ("trend", "rsi", "macd", "volume", "value")
_INPUTS = ("close", "ema20", "ema50", "rsi14", "macd_histogram", "volume_ratio", "value_ratio")


def _validate(config: dict[str, Any]) -> None:
    if config.get("screener_version") != "v2" or config.get("timeframe") != "1d":
        raise ValueError("Unsupported screener version/timeframe")
    if config.get("scoring_method") != "binary_weighted_sum":
        raise ValueError("Unsupported scoring_method")
    threshold = config.get("passing_score")
    if isinstance(threshold, bool) or not isinstance(threshold, int) or not 0 <= threshold <= 100:
        raise ValueError("passing_score must be integer from 0 to 100")
    if tuple(config.get("required_inputs", ())) != _INPUTS:
        raise ValueError("V2 required_inputs must match the evaluator contract")
    rules = config.get("rules")
    if not isinstance(rules, list) or tuple(x.get("id") for x in rules if isinstance(x, dict)) != _RULE_IDS or len(rules) != len(_RULE_IDS):
        raise ValueError("V2 rule identifiers/order must match the evaluator")
    specs = [
        ("ema_stack", None),
        ("range_inclusive", "rsi14"),
        ("greater_than", "macd_histogram"),
        ("greater_or_equal", "volume_ratio"),
        ("greater_or_equal", "value_ratio"),
    ]
    total = 0
    for rule, (kind, field) in zip(rules, specs):
        if rule.get("kind") != kind or (field is not None and rule.get("field") != field):
            raise ValueError(f"Invalid rule kind/field: {rule.get('id')}")
        weight = rule.get("weight")
        if isinstance(weight, bool) or not isinstance(weight, int) or not 0 <= weight <= 100:
            raise ValueError(f"Invalid weight: {rule.get('id')}")
        total += weight
        if field == "rsi14":
            lo, hi = rule.get("min"), rule.get("max")
            if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (lo, hi)) or not 0 <= lo <= hi <= 100:
                raise ValueError("Invalid RSI limits")
        elif field is not None:
            number = rule.get("threshold")
            if not isinstance(number, (int, float)) or isinstance(number, bool):
                raise ValueError(f"Invalid threshold: {field}")
            if field in ("volume_ratio", "value_ratio") and number < 0:
                raise ValueError(f"Negative ratio threshold: {field}")
        if not rule.get("description_vi") or not rule.get("description_en"):
            raise ValueError(f"Missing methodology description: {rule.get('id')}")
    if total != 100:
        raise ValueError(f"All V2 weights must sum to 100; got {total}")


def load_v2() -> dict[str, Any]:
    """Load and validate JSON + EN/VI Markdown, then bind them by content hash."""
    config = json.loads((_ROOT / "configs" / "v2.json").read_text(encoding="utf-8"))
    _validate(config)
    en = (_ROOT / "methodologies" / "v2.md").read_text(encoding="utf-8")
    vi = (_ROOT / "methodologies" / "v2.vi.md").read_text(encoding="utf-8")
    if not en.strip() or not vi.strip():
        raise ValueError("Methodology must exist in both languages")
    payload = {"config": config, "methodology_md": en, "methodology_vi_md": vi}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "screener_version": "v2",
        "config_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "config": config,
        "methodology_md": en,
        "methodology_vi_md": vi,
    }


def _get_registered(db: SupabaseClient, version: str) -> dict[str, Any] | None:
    result = db._with_retry(
        lambda: db.get().table("screener_configs")
        .select("screener_version,config_hash")
        .eq("screener_version", version).limit(1).execute(),
        action_name=f"fetch screener config version={version}",
    )
    rows = result.data or []
    return rows[0] if rows else None


def assert_registered(db: SupabaseClient, profile: dict[str, Any]) -> None:
    """Fail closed on absent/mismatched registry before result writes."""
    stored = _get_registered(db, profile["screener_version"])
    if not stored:
        raise ValueError("Screener V2 is not registered; run stock-screener-config --version v2 --apply after migration")
    if stored.get("config_hash") != profile["config_hash"]:
        raise ValueError("Registered screener config hash differs: create a new screener version, do not mutate V2")


def describe_config(version: str = "v2", language: str = "vi", apply: bool = False, db: SupabaseClient | None = None) -> dict[str, Any]:
    if version != "v2" or language not in ("vi", "en"):
        raise ValueError("Only V2 and language vi/en are supported")
    profile = load_v2()
    if apply:
        client = db if db is not None else SupabaseClient()
        stored = _get_registered(client, version)
        if stored is not None:
            if stored.get("config_hash") != profile["config_hash"]:
                raise ValueError("An immutable V2 config already exists with a different hash; create V3 instead")
        else:
            record = {**profile, "created_at": app_now_iso()}
            client._with_retry(
                lambda: client.get().table("screener_configs").insert(record).execute(),
                action_name="register immutable screener V2 configuration",
            )
    return {
        "status": "OK", "screener_version": version,
        "config_hash": profile["config_hash"],
        "mode": "register" if apply else "preview",
        "config": profile["config"],
        "methodology": profile["methodology_vi_md"] if language == "vi" else profile["methodology_md"],
    }
