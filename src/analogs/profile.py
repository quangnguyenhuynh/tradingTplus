"""Immutable Historical Analog profile configuration."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

DEFAULT_PROFILE_PATH = (
    Path(__file__).parent / "profiles" / "tplus_analog_core_eod_v1.json"
)


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def config_hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AnalogProfile:
    config: dict[str, Any]
    config_hash: str

    @property
    def code(self) -> str:
        return str(self.config["profile_code"])

    @property
    def version(self) -> int:
        return int(self.config["version"])

    @property
    def weights(self) -> dict[str, float]:
        return {row["name"]: float(row["weight"]) for row in self.config["dimensions"]}


def validate_profile(config: Mapping[str, Any]) -> None:
    required = {
        "profile_code",
        "version",
        "timeframe",
        "checkpoint",
        "horizons",
        "maximum_lookback_years",
        "top_k",
        "minimum_sample",
        "normalization",
        "distance_metric",
        "similarity_transform",
        "distance_threshold",
        "status",
        "dimensions",
    }
    if set(config) != required:
        raise ValueError(f"profile keys must be exactly {sorted(required)}")
    if config["timeframe"] != "1d" or config["checkpoint"] != "EOD":
        raise ValueError("V1 requires timeframe=1d and checkpoint=EOD")
    if config["horizons"] != [1, 3, 5]:
        raise ValueError("V1 horizons must be [1, 3, 5]")
    dimensions = config["dimensions"]
    names = [row.get("name") for row in dimensions]
    expected = [
        "return_5d",
        "price_vs_ema20_pct",
        "ema20_vs_ema50_pct",
        "rsi14",
        "macd_histogram_pct",
        "distance_to_high20_pct",
        "volume_ratio",
        "value_ratio",
        "close_position_in_candle",
    ]
    if names != expected or any(
        not math.isfinite(float(row["weight"])) for row in dimensions
    ):
        raise ValueError(
            "V1 dimensions must have the exact ordered names and finite weights"
        )
    if not math.isclose(
        sum(float(row["weight"]) for row in dimensions), 1.0, abs_tol=1e-12
    ):
        raise ValueError("dimension weights must total 1.0")
    threshold = config["distance_threshold"]
    if threshold is not None and (
        not isinstance(threshold, (int, float))
        or threshold < 0
        or not math.isfinite(threshold)
    ):
        raise ValueError(
            "distance_threshold must be null or a finite non-negative number"
        )


def load_profile(path: str | Path = DEFAULT_PROFILE_PATH) -> AnalogProfile:
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_profile(config)
    return AnalogProfile(config=config, config_hash=config_hash(config))
