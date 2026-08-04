from types import MappingProxyType
from typing import Any, Mapping

from .base import Strategy, decision


class BreakoutV1(Strategy):
    strategy_code = "BREAKOUT_V1"
    version = 1
    config = MappingProxyType({"daily_volume_ratio_min": 1.2, "intraday_rsi_min": 50.0})
    scan_timeframes = MappingProxyType({slot: ("15m", "60m") for slot in ("09:30", "11:30", "13:30", "14:30")})

    def daily_setup(self, row: Mapping[str, Any]):
        needed = ("close_above_high_20", "volume_ratio")
        if row.get("timeframe") != "1d" or any(row.get(k) is None for k in needed):
            return decision(passed=False, status="not_evaluable", reasons=["missing_required_daily_features"], metrics={}, rows=[row])
        metrics = {k: row[k] for k in needed}
        passed = bool(row["close_above_high_20"]) and float(row["volume_ratio"]) >= self.config["daily_volume_ratio_min"]
        return decision(passed=passed, status="passed" if passed else "failed", reasons=["daily_breakout_and_liquidity"] if passed else ["daily_breakout_conditions_failed"], metrics=metrics, rows=[row])

    def intraday_confirm(self, setup: Mapping[str, Any], rows: Mapping[str, Mapping[str, Any]], scan_slot: str):
        required = self.required_timeframes(scan_slot)
        if any(tf not in rows for tf in required):
            return decision(passed=False, status="not_evaluable", reasons=["missing_required_intraday_timeframe"], metrics={}, rows=rows.values())
        used = [rows[tf] for tf in required]
        if any(r.get("close_above_vwap") is None or r.get("rsi14") is None for r in used):
            return decision(passed=False, status="not_evaluable", reasons=["missing_required_intraday_features"], metrics={}, rows=used)
        passed = all(bool(r["close_above_vwap"]) and float(r["rsi14"]) >= self.config["intraday_rsi_min"] for r in used)
        return decision(passed=passed, status="passed" if passed else "failed", reasons=["intraday_breakout_confirmed"] if passed else ["intraday_breakout_conditions_failed"], metrics={tf: {"rsi14": rows[tf]["rsi14"], "close_above_vwap": rows[tf]["close_above_vwap"]} for tf in required}, rows=used)
