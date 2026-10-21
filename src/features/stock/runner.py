"""Backward-compatible mixed feature routing.

Daily and intraday implementations live in their source-specific modules. This
module keeps the historical mixed entrypoints without duplicating either flow.
"""

from __future__ import annotations

import logging

import pandas as pd

from .common import (
    FEATURE_COLUMNS,
    INTRADAY_TIMEFRAMES,
    SUPPORTED_TIMEFRAMES,
    calculate_macd,
    calculate_rsi,
    nullable_comparison,
    safe_div,
)
from .daily import (
    calculate_daily_features_for_symbol,
    compute_daily_features,
    run_daily_features_with_summary,
)
from .intraday import (
    aggregate_timeframe,
    calculate_intraday_features_for_symbol,
    compute_intraday_features,
    filter_closed_buckets,
    run_intraday_features_with_summary,
)
from .runtime import (
    DEFAULT_FEATURE_TIMEFRAMES,
    build_feature_records,
    normalize_timeframes,
)

logger = logging.getLogger(__name__)

# Compatibility aliases retained for existing internal/debug imports.
_build_feature_records = build_feature_records
_normalize_timeframes = normalize_timeframes


def compute_feature_dataframe(
    df: pd.DataFrame,
    daily_df: pd.DataFrame | None = None,
    timeframe: str = "1m",
) -> pd.DataFrame:
    """Compatibility wrapper; prefer the source-specific calculator."""
    if timeframe == "1d":
        return compute_daily_features(df)
    return compute_intraday_features(
        df,
        timeframe=timeframe,
        daily_df=daily_df,
    )


def run_feature_engine_with_summary(
    symbols=None,
    mode="full",
    timeframes=None,
    target_date=None,
    as_of=None,
):
    """Compatibility orchestrator for explicitly requested source flows."""
    normalized = normalize_timeframes(timeframes)
    daily_requested = "1d" in normalized
    intraday_requested = tuple(
        timeframe for timeframe in normalized if timeframe != "1d"
    )
    summaries = []
    if daily_requested:
        summaries.append(
            run_daily_features_with_summary(
                symbols,
                mode,
                target_date,
            )
        )
    if intraday_requested:
        summaries.append(
            run_intraday_features_with_summary(
                symbols,
                mode,
                intraday_requested,
                target_date,
                as_of,
            )
        )

    warning = (
        "features is a compatibility orchestrator; prefer "
        "features-daily or features-intraday."
    )
    if len(summaries) == 1:
        result = dict(summaries[0])
        result["compatibility_warning"] = warning
        result["flow"] = "features"
        return result

    total = sum(summary["total_records"] for summary in summaries)
    errors = [
        error
        for summary in summaries
        for error in summary["errors"]
    ]
    statuses = {summary["status"] for summary in summaries}
    return {
        "flow": "features",
        "mode": mode,
        "target_date": summaries[0]["target_date"] if summaries else None,
        "total_records": total,
        "records_by_timeframe": {
            key: value
            for summary in summaries
            for key, value in summary["records_by_timeframe"].items()
        },
        "source_summaries": summaries,
        "errors": errors,
        "status": (
            "FAILED"
            if statuses == {"FAILED"}
            else (
                "PARTIAL"
                if "FAILED" in statuses or "PARTIAL" in statuses
                else "OK"
            )
        ),
        "compatibility_warning": warning,
    }


def run_feature_engine(
    symbols=None,
    mode="full",
    timeframes=None,
    target_date=None,
):
    return run_feature_engine_with_summary(
        symbols,
        mode,
        timeframes,
        target_date,
    )["total_records"]


def calculate_features_for_symbol_full_chunked(
    symbol,
    timeframes=None,
    upsert_batch_size=1000,
):
    """Compatibility wrapper for a full source-isolated feature run."""
    normalized = normalize_timeframes(timeframes)
    total = 0
    if "1d" in normalized:
        total += calculate_daily_features_for_symbol(
            symbol,
            mode="full",
            upsert_batch_size=upsert_batch_size,
        )
    intraday_timeframes = tuple(
        timeframe for timeframe in normalized if timeframe != "1d"
    )
    if intraday_timeframes:
        total += calculate_intraday_features_for_symbol(
            symbol,
            timeframes=intraday_timeframes,
            mode="full",
            upsert_batch_size=upsert_batch_size,
        )
    return total


def calculate_features_for_symbol_incremental(
    symbol,
    timeframes=None,
    target_date=None,
    warmup_bars=None,
    upsert_batch_size=1000,
    records_by_timeframe=None,
):
    """Compatibility wrapper; warmup_bars is ignored by all-history Phase 0."""
    normalized = normalize_timeframes(timeframes)
    total = 0
    if "1d" in normalized:
        total += calculate_daily_features_for_symbol(
            symbol,
            mode="incremental",
            target_date=target_date,
            upsert_batch_size=upsert_batch_size,
            records_by_timeframe=records_by_timeframe,
        )
    intraday_timeframes = tuple(
        timeframe for timeframe in normalized if timeframe != "1d"
    )
    if intraday_timeframes:
        total += calculate_intraday_features_for_symbol(
            symbol,
            timeframes=intraday_timeframes,
            mode="incremental",
            target_date=target_date,
            upsert_batch_size=upsert_batch_size,
            records_by_timeframe=records_by_timeframe,
        )
    return total


def calculate_features_for_symbol(symbol, timeframe="1m"):
    """Compatibility wrapper for older maintenance utilities."""
    return calculate_features_for_symbol_full_chunked(
        symbol,
        [timeframe],
    )


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    parser = argparse.ArgumentParser(description="Run feature engine")
    parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default="full",
    )
    parser.add_argument(
        "--timeframes",
        nargs="*",
        default=list(DEFAULT_FEATURE_TIMEFRAMES),
    )
    parser.add_argument(
        "--symbols",
        nargs="*",
        default=["SSI", "SHB", "HPG", "FPT"],
    )
    args = parser.parse_args()
    logger.info(
        "Symbols: %s mode=%s timeframes=%s",
        args.symbols,
        args.mode,
        args.timeframes,
    )
    run_feature_engine(
        args.symbols,
        mode=args.mode,
        timeframes=args.timeframes,
    )
