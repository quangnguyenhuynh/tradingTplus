"""Simple rule-based backtest engine.

The MVP backtester pairs historical trading signals with future feature rows to
estimate one-position-at-a-time PnL. It is intentionally small and dependency
light so it can be unit tested without a live Supabase connection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

import pandas as pd

from src.database.client import SupabaseClient


BUY_SIGNALS = {"BUY", "LONG", "BULLISH", "REVERSAL_BUY", "BREAKOUT_BUY", "TREND_BUY"}
SELL_SIGNALS = {"SELL", "SHORT", "BEARISH", "REVERSAL_SELL", "BREAKOUT_SELL", "TREND_SELL"}


@dataclass(frozen=True)
class BacktestConfig:
    """Configuration for the MVP backtest."""

    initial_capital: float = 100_000_000.0
    position_size_pct: float = 1.0
    holding_bars: int = 5
    fee_pct: float = 0.001
    min_score: float = 0.0
    max_entry_staleness_minutes: int = 2

    def __post_init__(self):
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if not 0 < self.position_size_pct <= 1:
            raise ValueError("position_size_pct must be in (0, 1]")
        if self.holding_bars <= 0:
            raise ValueError("holding_bars must be positive")
        if self.fee_pct < 0:
            raise ValueError("fee_pct must be non-negative")
        if self.max_entry_staleness_minutes < 0:
            raise ValueError("max_entry_staleness_minutes must be non-negative")


def _normalize_signal_type(value: object) -> str:
    return str(value or "").strip().upper()


def _signal_direction(signal_type: object) -> int:
    normalized = _normalize_signal_type(signal_type)
    if normalized in BUY_SIGNALS or "BUY" in normalized or "LONG" in normalized:
        return 1
    if normalized in SELL_SIGNALS or "SELL" in normalized or "SHORT" in normalized:
        return -1
    return 0


def _prepare_frame(rows: Iterable[dict], required_columns: set[str]) -> pd.DataFrame:
    df = pd.DataFrame(list(rows))
    if df.empty:
        return df
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    df = df.copy()
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df.sort_values(["symbol", "time"]).reset_index(drop=True)


def run_backtest(
    features: Iterable[dict],
    signals: Iterable[dict],
    config: BacktestConfig | None = None,
) -> dict:
    """Run a deterministic MVP backtest from feature and signal records.

    Assumptions:
    - each intraday signal opens at the latest feature close at or before signal
      time only when it is within ``max_entry_staleness_minutes``;
    - the trade exits after ``holding_bars`` future feature rows for the same symbol/timeframe;
    - overlapping trades for the same symbol are skipped to keep accounting simple.
    """
    config = config or BacktestConfig()
    feature_df = _prepare_frame(features, {"symbol", "time", "close"})
    signal_df = _prepare_frame(signals, {"symbol", "time", "signal_type"})

    if feature_df.empty or signal_df.empty:
        return _build_summary(config.initial_capital, [])

    if "timeframe" not in feature_df.columns:
        feature_df["timeframe"] = "1m"
    if "timeframe" not in signal_df.columns:
        signal_df["timeframe"] = "1m"
    if "score" not in signal_df.columns:
        signal_df["score"] = 0.0

    trades = []
    capital = config.initial_capital
    open_until: dict[tuple[str, str], pd.Timestamp] = {}

    grouped_features = {
        key: group.sort_values("time").reset_index(drop=True)
        for key, group in feature_df.groupby(["symbol", "timeframe"], dropna=False)
    }

    for signal in signal_df.sort_values("time").to_dict("records"):
        if float(signal.get("score") or 0) < config.min_score:
            continue
        direction = _signal_direction(signal.get("signal_type"))
        if direction == 0:
            continue

        key = (signal["symbol"], signal.get("timeframe", "1m"))
        candles = grouped_features.get(key)
        if candles is None or candles.empty:
            continue
        if open_until.get(key) and signal["time"] <= open_until[key]:
            continue

        eligible = candles[candles["time"] <= signal["time"]]
        if eligible.empty:
            continue
        entry_idx = int(eligible.index[-1])
        entry_time = candles.iloc[entry_idx]["time"]
        if key[1] != "1d" and signal["time"] - entry_time > timedelta(minutes=config.max_entry_staleness_minutes):
            continue
        exit_idx = entry_idx + config.holding_bars
        if exit_idx >= len(candles):
            continue

        entry = candles.iloc[entry_idx]
        exit_ = candles.iloc[exit_idx]
        entry_price = float(entry["close"])
        exit_price = float(exit_["close"])
        if entry_price <= 0 or exit_price <= 0:
            continue

        notional = capital * config.position_size_pct
        gross_return = direction * ((exit_price - entry_price) / entry_price)
        net_return = gross_return - (config.fee_pct * 2)
        pnl = notional * net_return
        capital += pnl
        open_until[key] = exit_["time"]
        trades.append(
            {
                "symbol": key[0],
                "timeframe": key[1],
                "direction": "long" if direction == 1 else "short",
                "entry_time": entry["time"].isoformat(),
                "exit_time": exit_["time"].isoformat(),
                "entry_price": entry_price,
                "exit_price": exit_price,
                "pnl": pnl,
                "return_pct": net_return * 100,
                "capital_after": capital,
            }
        )

    return _build_summary(capital, trades, config.initial_capital)


def _build_summary(final_capital: float, trades: list[dict], initial_capital: float | None = None) -> dict:
    initial = final_capital if initial_capital is None else initial_capital
    total = len(trades)
    wins = sum(1 for trade in trades if trade["pnl"] > 0)
    losses = sum(1 for trade in trades if trade["pnl"] < 0)
    returns = pd.Series([trade["return_pct"] / 100 for trade in trades], dtype="float64")
    equity = pd.Series([initial] + [trade["capital_after"] for trade in trades], dtype="float64")
    drawdown = (equity / equity.cummax()) - 1
    sharpe = (
        0.0
        if returns.empty or returns.std(ddof=0) == 0
        else float((returns.mean() / returns.std(ddof=0)) * (252 ** 0.5))
    )
    return {
        "initial_capital": initial,
        "final_capital": final_capital,
        "total_pnl": final_capital - initial,
        "total_return_pct": ((final_capital / initial) - 1) * 100 if initial else 0.0,
        "trade_count": total,
        "win_count": wins,
        "loss_count": losses,
        "win_rate_pct": (wins / total * 100) if total else 0.0,
        "max_drawdown_pct": abs(float(drawdown.min() * 100)) if not drawdown.empty else 0.0,
        "sharpe": sharpe,
        "trades": trades,
    }


def load_backtest_inputs(
    target_date: str,
    timeframe: str = "1m",
) -> tuple[list[dict], list[dict]]:
    db = SupabaseClient()
    features = (
        db.get()
        .table("features")
        .select("symbol,timeframe,time,close")
        .eq("timeframe", timeframe)
        .gte("time", f"{target_date} 00:00:00")
        .lte("time", f"{target_date} 23:59:59")
        .execute()
        .data
    )
    signals = (
        db.get()
        .table("trading_signals")
        .select("symbol,timeframe,time,signal_type,score")
        .eq("timeframe", timeframe)
        .gte("time", f"{target_date} 00:00:00")
        .lte("time", f"{target_date} 23:59:59")
        .execute()
        .data
    )
    return features, signals


def run_backtest_engine(
    target_date: str | None = None,
    timeframe: str = "1m",
    config: BacktestConfig | None = None,
) -> dict:
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")
    features, signals = load_backtest_inputs(target_date, timeframe)
    result = run_backtest(features, signals, config)
    print(
        f"📈 Backtest {target_date} {timeframe}: "
        f"{result['trade_count']} trades, "
        f"PnL={result['total_pnl']:.0f}, "
        f"Return={result['total_return_pct']:.2f}%"
    )
    return result


if __name__ == "__main__":
    run_backtest_engine()
