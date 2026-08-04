"""Stable contracts shared by live scanning and historical replay."""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True)
class RuleDecision:
    passed: bool
    status: str
    reasons: tuple[str, ...]
    metrics: Mapping[str, Any]
    input_feature_keys: tuple[tuple[str, str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "status": self.status,
                "reasons": list(self.reasons), "metrics": dict(self.metrics),
                "input_feature_keys": [list(key) for key in self.input_feature_keys]}


def feature_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("symbol", "")), str(row.get("timeframe", "")), str(row.get("time", "")))


def decision(*, passed: bool, status: str, reasons: list[str], metrics: dict, rows=()) -> RuleDecision:
    return RuleDecision(passed, status, tuple(reasons), MappingProxyType(metrics), tuple(feature_key(row) for row in rows))


class Strategy(ABC):
    strategy_code: str
    version: int
    daily_timeframe = "1d"
    config: Mapping[str, Any]
    scan_timeframes: Mapping[str, tuple[str, ...]]

    @property
    def config_hash(self) -> str:
        payload = json.dumps(dict(self.config), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    @abstractmethod
    def daily_setup(self, features_1d: Mapping[str, Any]) -> RuleDecision: ...

    @abstractmethod
    def intraday_confirm(self, setup: Mapping[str, Any], intraday_features: Mapping[str, Mapping[str, Any]], scan_slot: str) -> RuleDecision: ...

    def required_timeframes(self, scan_slot: str) -> tuple[str, ...]:
        if scan_slot not in self.scan_timeframes:
            raise ValueError(f"Unsupported scan slot for {self.strategy_code}: {scan_slot}")
        return self.scan_timeframes[scan_slot]
