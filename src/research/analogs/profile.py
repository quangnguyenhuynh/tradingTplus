"""Immutable Historical Analog profile configuration."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

PROFILE_DIRECTORY = Path(__file__).parent / "profiles"
DEFAULT_PROFILE_CODE = "TPLUS_ANALOG_CORE_EOD"
DEFAULT_PROFILE_VERSION = 1
SOURCE_PROFILES = {
    (DEFAULT_PROFILE_CODE, 1): PROFILE_DIRECTORY / "tplus_analog_core_eod_v1.json",
    (DEFAULT_PROFILE_CODE, 2): PROFILE_DIRECTORY / "tplus_analog_core_eod_v2.json",
}
DEFAULT_PROFILE_PATH = SOURCE_PROFILES[(DEFAULT_PROFILE_CODE, DEFAULT_PROFILE_VERSION)]


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
        "matching_strategy",
        "quality_calibration",
        "status",
        "dimensions",
    }
    if set(config) != required:
        raise ValueError(f"profile keys must be exactly {sorted(required)}")
    code = config["profile_code"]
    version = config["version"]
    supported_horizons = {
        (DEFAULT_PROFILE_CODE, 1): [1, 3, 5],
        (DEFAULT_PROFILE_CODE, 2): [1, 3, 5, 10],
    }
    expected_horizons = supported_horizons.get((code, version))
    if expected_horizons is None:
        raise ValueError(f"unsupported source profile: {code} version {version}")
    if config["timeframe"] != "1d" or config["checkpoint"] != "EOD":
        raise ValueError("EOD profiles require timeframe=1d and checkpoint=EOD")
    if config["horizons"] != expected_horizons:
        raise ValueError(
            f"{code} version {version} horizons must be {expected_horizons} in order"
        )
    fixed_contract = {
        "maximum_lookback_years": 5,
        "normalization": "median_iqr",
        "distance_metric": "weighted_euclidean",
        "similarity_transform": "exp_negative_distance",
    }
    if any(config[key] != value for key, value in fixed_contract.items()):
        raise ValueError("EOD profiles must preserve the fixed matching contract")
    if not isinstance(config["top_k"], int) or config["top_k"] <= 0:
        raise ValueError("top_k must be a positive integer")
    if config["minimum_sample"] != config["top_k"]:
        raise ValueError("minimum_sample must equal top_k for exact top-k matching")
    if config["matching_strategy"] != "nearest_top_k":
        raise ValueError("EOD profiles require matching_strategy=nearest_top_k")
    if config["quality_calibration"] != "walk_forward_d_k":
        raise ValueError("EOD profiles require walk-forward d_k quality calibration")
    if config["status"] not in {
        "draft",
        "validated",
        "approved",
        "rejected",
        "retired",
    }:
        raise ValueError("unsupported profile status")
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
    expected_formulas = [
        "close[D] / close[D-5 trading sessions] - 1",
        "close / ema20 - 1",
        "ema20 / ema50 - 1",
        "features.rsi14",
        "macd_histogram / close",
        "close / high_20_bars - 1",
        "features.volume_ratio",
        "features.value_ratio",
        "(close - low) / (high - low)",
    ]
    expected_weights = [0.10, 0.15, 0.15, 0.10, 0.10, 0.15, 0.075, 0.075, 0.10]
    if not math.isclose(
        sum(float(row["weight"]) for row in dimensions), 1.0, abs_tol=1e-12
    ):
        raise ValueError("dimension weights must total 1.0")
    if [row.get("formula") for row in dimensions] != expected_formulas or any(
        not math.isclose(float(row["weight"]), weight, abs_tol=1e-12)
        for row, weight in zip(dimensions, expected_weights)
    ):
        raise ValueError("EOD dimensions must preserve the exact formulas and weights")
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


def load_source_profile(
    profile_code: str = DEFAULT_PROFILE_CODE,
    version: int = DEFAULT_PROFILE_VERSION,
    requested_hash: str | None = None,
) -> AnalogProfile:
    """Load one exact source-controlled profile; never substitute latest."""
    path = SOURCE_PROFILES.get((profile_code, version))
    if path is None:
        raise ValueError(f"SOURCE_PROFILE_NOT_FOUND:{profile_code}:v{version}")
    profile = load_profile(path)
    if requested_hash is not None and requested_hash != profile.config_hash:
        raise ValueError("SOURCE_PROFILE_CONFIG_HASH_MISMATCH")
    return profile
