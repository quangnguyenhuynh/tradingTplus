"""Pure Index Daily Feature V1 calculations from normalized ``index_daily`` rows."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.common import calculate_macd, calculate_rsi, safe_div

SOURCE_COLUMNS = (
    "index_code", "trading_date", "index_value", "total_vol", "total_val",
    "total_match_vol", "total_match_val", "total_deal_vol", "total_deal_val",
    "advances", "no_changes", "declines", "ceilings", "floors",
)

FEATURE_COLUMNS = (
    "index_return_1d", "index_return_3d", "index_return_5d", "index_return_10d",
    "index_ma20", "index_ma50", "index_distance_ma20", "index_distance_ma50",
    "index_rsi14", "index_macd", "index_macd_signal", "index_macd_histogram",
    "index_volatility_20d", "index_drawdown_20d", "index_drawdown_60d",
    "index_breadth_net", "index_breadth_ratio", "index_advance_pct",
    "index_decline_pct", "index_unchanged_pct", "index_ceiling_pct",
    "index_floor_pct", "index_limit_balance", "index_breadth_ma5",
    "index_breadth_ma10", "index_total_vol_ma20", "index_total_vol_ratio20",
    "index_total_val_ma20", "index_total_val_ratio20", "index_match_vol_ratio",
    "index_match_val_ratio", "index_deal_vol_ratio", "index_deal_val_ratio",
)


def compute_index_daily_features(source: pd.DataFrame) -> pd.DataFrame:
    """Calculate V1 features without filling missing source values or sessions."""
    if source.empty:
        return pd.DataFrame(columns=(*SOURCE_COLUMNS[:4], "breadth_total", *FEATURE_COLUMNS))
    missing = [column for column in SOURCE_COLUMNS if column not in source.columns]
    if missing:
        raise ValueError(f"Missing index_daily columns: {missing}")
    codes = source["index_code"].dropna().astype(str).unique()
    if len(codes) != 1:
        raise ValueError("Index features must be calculated for exactly one index_code")

    out = source.loc[:, SOURCE_COLUMNS].copy()
    out["trading_date"] = pd.to_datetime(out["trading_date"], errors="coerce")
    if out["trading_date"].isna().any():
        raise ValueError("index_daily contains an invalid trading_date")
    out = out.sort_values("trading_date").drop_duplicates("trading_date", keep="last").reset_index(drop=True)
    numeric = SOURCE_COLUMNS[2:]
    for column in numeric:
        out[column] = pd.to_numeric(out[column], errors="coerce")

    value = out["index_value"]
    for sessions in (1, 3, 5, 10):
        out[f"index_return_{sessions}d"] = safe_div(value, value.shift(sessions), out.index) - 1
    out["index_ma20"] = value.rolling(20, min_periods=20).mean()
    out["index_ma50"] = value.rolling(50, min_periods=50).mean()
    out["index_distance_ma20"] = safe_div(value, out["index_ma20"], out.index) - 1
    out["index_distance_ma50"] = safe_div(value, out["index_ma50"], out.index) - 1
    out["index_rsi14"] = calculate_rsi(value, 14)
    out["index_macd"], out["index_macd_signal"], out["index_macd_histogram"] = calculate_macd(value)
    out["index_volatility_20d"] = out["index_return_1d"].rolling(20, min_periods=20).std()
    out["index_drawdown_20d"] = safe_div(value, value.rolling(20, min_periods=20).max(), out.index) - 1
    out["index_drawdown_60d"] = safe_div(value, value.rolling(60, min_periods=60).max(), out.index) - 1

    out["breadth_total"] = out[["advances", "no_changes", "declines"]].sum(axis=1, min_count=3)
    out["index_breadth_net"] = out["advances"] - out["declines"]
    denominator = out["breadth_total"]
    for target, numerator in (
        ("index_breadth_ratio", out["index_breadth_net"]),
        ("index_advance_pct", out["advances"]),
        ("index_decline_pct", out["declines"]),
        ("index_unchanged_pct", out["no_changes"]),
        ("index_ceiling_pct", out["ceilings"]),
        ("index_floor_pct", out["floors"]),
        ("index_limit_balance", out["ceilings"] - out["floors"]),
    ):
        out[target] = safe_div(numerator, denominator, out.index)
    out["index_breadth_ma5"] = out["index_breadth_ratio"].rolling(5, min_periods=5).mean()
    out["index_breadth_ma10"] = out["index_breadth_ratio"].rolling(10, min_periods=10).mean()

    for kind in ("vol", "val"):
        total = out[f"total_{kind}"]
        average = total.rolling(20, min_periods=20).mean()
        out[f"index_total_{kind}_ma20"] = average
        out[f"index_total_{kind}_ratio20"] = safe_div(total, average, out.index)
        out[f"index_match_{kind}_ratio"] = safe_div(out[f"total_match_{kind}"], total, out.index)
        out[f"index_deal_{kind}_ratio"] = safe_div(out[f"total_deal_{kind}"], total, out.index)

    out = out.replace([np.inf, -np.inf], np.nan)
    return out[["index_code", "trading_date", "index_value", "total_vol", "total_val", "breadth_total", *FEATURE_COLUMNS]]
