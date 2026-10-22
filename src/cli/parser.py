from __future__ import annotations
from src.features import DEFAULT_PERSISTED_FEATURE_TIMEFRAMES, PERSISTED_INTRADAY_TIMEFRAMES
from src.ingest import daily_run
import argparse
import json
from typing import Any

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TradingTPlus production flows")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sync-master-data", help="Sync SSI master data into DB")
    sub.add_parser("init", help="Alias for sync-master-data")

    daily = sub.add_parser(
        "daily",
        help="Daily SSI ingest only; no features/signals/backtests",
    )
    daily.add_argument(
        "date",
        nargs="?",
        help="Trading date DD/MM/YYYY; defaults to latest previous weekday",
    )
    daily.add_argument("--data-source", default=None, help="Production source (default: newest ready source for stock_daily)")

    index_daily = sub.add_parser("index-daily", help="SSI index daily raw + validated clean ingest only")
    index_daily.add_argument("date", nargs="?", help="Trading date YYYY-MM-DD or DD/MM/YYYY; defaults to latest weekday on/before today in Vietnam")
    index_daily.add_argument("--indexes", nargs="+", default=None, help="Index codes; omitted means active index_master rows")
    index_daily.add_argument("--data-source", default=None, help="Production source (default: newest ready source for index_daily)")

    index_backfill = sub.add_parser("index-backfill", help="Inclusive index daily source-data backfill")
    index_backfill.add_argument("--from", "--from-date", dest="from_date", required=True, help="Inclusive start date YYYY-MM-DD or DD/MM/YYYY")
    index_backfill.add_argument("--to", "--to-date", dest="to_date", required=True, help="Inclusive end date YYYY-MM-DD or DD/MM/YYYY")
    index_backfill.add_argument("--indexes", nargs="+", default=None)
    index_backfill.add_argument("--data-source", default=None)

    index_check = sub.add_parser("index-check", help="Read-only index raw/clean completeness check")
    index_check.add_argument("date", nargs="?", help="Trading date YYYY-MM-DD or DD/MM/YYYY; defaults to latest previous weekday")
    index_check.add_argument("--indexes", nargs="+", default=None)

    index_preview = sub.add_parser(
        "index-preview",
        help="Read-only SSI index daily preview; never reads or writes database rows",
    )
    preview_dates = index_preview.add_mutually_exclusive_group(required=True)
    preview_dates.add_argument("--date", help="Trading date YYYY-MM-DD or DD/MM/YYYY")
    preview_dates.add_argument("--from", dest="from_date", help="Inclusive start date YYYY-MM-DD or DD/MM/YYYY")
    index_preview.add_argument("--to", dest="to_date", help="Inclusive end date (required with --from)")
    index_preview.add_argument(
        "--indexes",
        required=True,
        help="Comma-separated index codes, for example VNINDEX,HNXINDEX",
    )
    preview_output = index_preview.add_mutually_exclusive_group()
    preview_output.add_argument("--raw", action="store_true", help="Print SSI payload rows as JSON")
    preview_output.add_argument("--json", action="store_true", dest="as_json", help="Print normalized rows as JSON")

    for command, help_text in (
        ("index-features-preview", "Read-only Index Daily Feature V1 calculation"),
        ("index-features-daily", "Calculate and upsert one clean index_daily date"),
    ):
        feature_parser = sub.add_parser(command, help=help_text)
        feature_parser.add_argument("--date", required=True, help="Trading date YYYY-MM-DD or DD/MM/YYYY")
        feature_parser.add_argument("--indexes", nargs="+", default=None, help="Index codes; omitted means active index_master rows")
    index_feature_backfill = sub.add_parser("index-features-backfill", help="Inclusive Index Daily Feature V1 backfill")
    index_feature_backfill.add_argument("--from", dest="from_date", required=True)
    index_feature_backfill.add_argument("--to", dest="to_date", required=True)
    index_feature_backfill.add_argument("--indexes", nargs="+", default=None)
    index_feature_check = sub.add_parser("index-features-check", help="Read-only index feature completeness check")
    index_feature_check.add_argument("--from", dest="from_date", required=True)
    index_feature_check.add_argument("--to", dest="to_date", required=True)
    index_feature_check.add_argument("--indexes", nargs="+", default=None)

    foreign_preview = sub.add_parser("foreign-features-preview", help="Read-only foreign EOD feature preview")
    foreign_preview.add_argument("--symbol", required=True)
    foreign_preview.add_argument("--date", required=True, help="DD/MM/YYYY")
    foreign_preview.add_argument("--calendar-file", help="Deprecated compatibility option; ignored")
    foreign_preview.add_argument("--json", action="store_true", dest="as_json")
    foreign_preview.add_argument("--show-source", action="store_true", help="Show the exact same-symbol rows used by the calculator")
    foreign_daily = sub.add_parser("foreign-features-daily", help="Calculate one explicit foreign EOD feature date")
    foreign_daily.add_argument("--date", required=True, help="DD/MM/YYYY")
    foreign_daily.add_argument("--symbols", nargs="+", default=None)
    foreign_daily.add_argument("--mode", choices=["target", "incremental"], default="target")
    foreign_daily.add_argument("--calendar-file", help="Deprecated compatibility option; ignored")
    foreign_daily.add_argument("--dry-run", action="store_true", help="Calculate and validate without writing feature rows")
    for command, help_text in (("foreign-features-backfill", "Inclusive foreign EOD feature backfill"), ("foreign-features-check", "Read-only foreign feature validation")):
        fp = sub.add_parser(command, help=help_text)
        fp.add_argument("--from", dest="from_date", required=True, help="DD/MM/YYYY")
        fp.add_argument("--to", dest="to_date", required=True, help="DD/MM/YYYY")
        fp.add_argument("--symbols", nargs="+", default=None)
        fp.add_argument("--calendar-file", help="Deprecated compatibility option; ignored")
        if command == "foreign-features-backfill":
            fp.add_argument("--dry-run", action="store_true", help="Calculate and validate without writing feature rows")
    rank = sub.add_parser("foreign-rank", help="Read-only get_foreign_ranking RPC")
    rank.add_argument("--date", required=True, help="DD/MM/YYYY")
    rank.add_argument("--ranking", required=True, choices=["attention", "accumulation", "distribution", "emerging"])
    rank.add_argument("--window", type=int, choices=[1, 5, 20], default=5)
    rank.add_argument("--sort", choices=["value", "ratio"], default="value")
    rank.add_argument("--market")
    rank.add_argument("--symbols", nargs="+", default=None)
    rank.add_argument("--top", type=int, default=20)
    rank.add_argument("--offset", type=int, default=0)
    history = sub.add_parser("foreign-symbol", help="Read-only get_foreign_symbol_history RPC")
    history.add_argument("--symbol", required=True)
    history.add_argument("--date", required=True, help="DD/MM/YYYY")
    history.add_argument("--lookback", type=int, default=20)
    daily.add_argument(
        "--symbols",
        nargs="+",
        default=None,
        help="Stock symbols to ingest; omitted means active master symbols",
    )

    intraday_ingest = sub.add_parser(
        "intraday-ingest",
        help="Production SSI IntradayOhlc 1m ingest only; no features/signals/backtests",
    )
    intraday_ingest.add_argument(
        "date",
        nargs="?",
        help="Trading date DD/MM/YYYY; defaults to latest previous weekday",
    )
    intraday_ingest.add_argument(
        "--symbols",
        nargs="+",
        default=None,
        help="Symbols to ingest; omitted means active master symbols",
    )
    intraday_ingest.add_argument("--data-source", default=None)

    stock_eod = sub.add_parser(
        "stock-eod",
        help="Stock EOD daily-only ingest and completeness; no intraday/indexes/features",
    )
    stock_eod.add_argument(
        "date",
        nargs="?",
        help="Trading date DD/MM/YYYY; defaults to latest previous weekday",
    )
    stock_eod.add_argument(
        "--symbols", nargs="+", default=None,
        help="Daily stock symbols intersected with status=active",
    )
    stock_eod.add_argument("--data-source", default=None)

    stock_daily = sub.add_parser("stock-daily", help="Alias for stock-eod")
    stock_daily.add_argument("date", nargs="?", help="Trading date YYYY-MM-DD or DD/MM/YYYY")
    stock_daily.add_argument("--symbols", nargs="+", default=None)
    stock_daily.add_argument("--data-source", default=None)

    stock_intraday = sub.add_parser(
        "stock-intraday",
        help="Guarded SSI v3 1m manual pilot; one symbol/date, read-only unless --write",
    )
    stock_intraday.add_argument(
        "date", nargs="?",
        help="Required explicit trading date DD/MM/YYYY or YYYY-MM-DD",
    )
    stock_intraday.add_argument(
        "--symbols", nargs="+", default=None,
        help="Exactly one explicit symbol; status and intraday_status must both be active",
    )
    stock_intraday.add_argument("--data-source", default=None)
    intraday_mode = stock_intraday.add_mutually_exclusive_group()
    intraday_mode.add_argument("--write", action="store_true", help="Persist the validated manual pilot")
    intraday_mode.add_argument("--dry-run", action="store_true", help="Explicit read-only mode (default)")

    for command, help_text in (
        (
            "backfill-daily",
            "Inclusive daily-only source-data backfill; no completeness/features/signals/backtests",
        ),
        (
            "backfill-intraday",
            "Inclusive 1m intraday-only source-data backfill; no daily/completeness/features/signals/backtests",
        ),
        (
            "backfill",
            "Inclusive daily + intraday source-data backfill with completeness; no features/signals/backtests",
        ),
    ):
        command_parser = sub.add_parser(command, help=help_text)
        command_parser.add_argument(
            "--from",
            "--from-date",
            dest="from_date",
            required=True,
            help="Inclusive start date DD/MM/YYYY",
        )
        command_parser.add_argument(
            "--to",
            "--to-date",
            dest="to_date",
            required=True,
            help="Inclusive end date DD/MM/YYYY",
        )
        command_parser.add_argument(
            "--symbols",
            nargs="+",
            default=None,
            help="Stock symbols used for every date; omitted means active master symbols",
        )
        command_parser.add_argument("--data-source", default=None)

    refill = sub.add_parser(
        "refill",
        help="Single-symbol source, completeness, and 1d/15m/60m feature refill",
    )
    refill.add_argument("--symbol", required=True, help="Exactly one stock symbol; ALL is forbidden")
    refill.add_argument(
        "--from", "--from-date", dest="from_date", required=True,
        help="Inclusive start date DD/MM/YYYY",
    )
    refill.add_argument(
        "--to", "--to-date", dest="to_date", required=True,
        help="Inclusive end date DD/MM/YYYY",
    )
    refill.add_argument("--data-source", default=None)

    features = sub.add_parser(
        "features",
        help="Compatibility feature router; persists only 1d, 15m, and 60m",
    )
    features.add_argument(
        "--mode",
        choices=["incremental", "full"],
        default="incremental",
        help=(
            "incremental uses per-stream watermarks and bounded warm-up; "
            "full recomputes and upserts all selected history without deleting"
        ),
    )
    features.add_argument(
        "--date",
        default=None,
        help="Target date DD/MM/YYYY for incremental mode",
    )
    features.add_argument(
        "--symbols",
        nargs="*",
        default=None,
        help="Symbols to process; omitted means all symbols",
    )
    features.add_argument(
        "--timeframes",
        nargs="*",
        default=list(DEFAULT_PERSISTED_FEATURE_TIMEFRAMES),
        help="Persisted feature timeframes: 15m 60m 1d",
    )

    features_daily = sub.add_parser(
        "features-daily",
        help="Explicit stock_daily-only 1d feature pipeline",
    )
    features_daily.add_argument(
        "--mode",
        choices=["incremental", "full", "replace", "rebuild-clean"],
        default="incremental",
        help=(
            "incremental uses a 5-year warm-up; full is non-destructive upsert; "
            "replace/rebuild-clean atomically replaces one exact scope"
        ),
    )
    features_daily.add_argument(
        "--date",
        default=None,
        help="Target date for incremental mode",
    )
    features_daily.add_argument(
        "--from",
        "--from-date",
        dest="from_date",
        default=None,
        help="Inclusive range start date DD/MM/YYYY",
    )
    features_daily.add_argument(
        "--to",
        "--to-date",
        dest="to_date",
        default=None,
        help="Inclusive range end date DD/MM/YYYY",
    )
    features_daily.add_argument("--symbols", nargs="*", default=None)

    features_intraday = sub.add_parser(
        "features-intraday",
        help="Explicit closed-candle 15m/60m feature pipeline from clean 1m source",
    )
    features_intraday.add_argument(
        "--mode",
        choices=["incremental", "full", "replace", "rebuild-clean"],
        default="incremental",
        help=(
            "incremental uses 250 observed sessions; full is non-destructive "
            "upsert; replace/rebuild-clean atomically replaces one exact scope"
        ),
    )
    features_intraday.add_argument(
        "--date",
        default=None,
        help="Target date for incremental mode",
    )
    features_intraday.add_argument(
        "--from",
        "--from-date",
        dest="from_date",
        default=None,
        help="Inclusive range start date DD/MM/YYYY",
    )
    features_intraday.add_argument(
        "--to",
        "--to-date",
        dest="to_date",
        default=None,
        help="Inclusive range end date DD/MM/YYYY",
    )
    features_intraday.add_argument("--symbols", nargs="*", default=None)
    features_intraday.add_argument(
        "--timeframes",
        nargs="*",
        default=list(PERSISTED_INTRADAY_TIMEFRAMES),
        help="Persisted intraday feature timeframes: 15m 60m",
    )
    features_intraday.add_argument(
        "--as-of",
        default=None,
        help="Safe cutoff: HH:MM Vietnam time or timezone-aware timestamp",
    )

    screener = sub.add_parser(
        "stock-screener", help="Research-only EOD technical screener; preview by default"
    )
    screener.add_argument("--date", required=True, help="Target trading date DD/MM/YYYY or YYYY-MM-DD")
    screener.add_argument("--symbols", nargs="+", default=None)
    screener.add_argument("--apply", action="store_true", help="Upsert exact-date results; default read-only")
    screener.add_argument("--version", choices=("v1", "v2"), default="v1",
                          help="Methodology version; V1 remains default for compatibility")
    screener_config = sub.add_parser("stock-screener-config", help="Review or register immutable V2 screener methodology")
    screener_config.add_argument("--version", choices=("v2",), default="v2")
    screener_config.add_argument("--language", choices=("vi", "en"), default="vi")
    screener_config.add_argument("--apply", action="store_true",
                                 help="Register immutable V2 config; default read-only")

    streaming = sub.add_parser(
        "streaming-ingest",
        help="Bounded SSI streaming ingest; dry-run/read-only unless --write is passed",
    )
    streaming.add_argument(
        "--symbols",
        nargs="*",
        default=[],
        help="Explicit symbols; never defaults to ALL",
    )
    streaming.add_argument(
        "--indexes",
        nargs="*",
        default=[],
        help="Explicit index codes for index channel",
    )
    streaming.add_argument(
        "--channels",
        nargs="*",
        required=True,
        choices=[
            "securities-status",
            "quote",
            "trade",
            "foreign-room",
            "index",
            "realtime-bar",
        ],
        help="Streaming channel groups to subscribe",
    )
    streaming.add_argument("--timeout", type=int, default=60)
    streaming.add_argument("--max-messages-per-channel", type=int, default=1)
    streaming.add_argument(
        "--write",
        action="store_true",
        default=False,
        help="Persist raw and valid clean rows; omitted means dry-run/read-only",
    )
    streaming.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Print sanitized debug summaries only",
    )

    analogs = sub.add_parser(
        "analogs", help="Phase 1 same-symbol EOD Historical Analog analysis"
    )
    analog_sub = analogs.add_subparsers(dest="analog_command", required=True)
    profiles = analog_sub.add_parser("profiles", help="Profile registry operations")
    profile_sub = profiles.add_subparsers(dest="profile_command", required=True)
    profile_sub.add_parser("list", help="List registered profiles")
    register = profile_sub.add_parser(
        "register", aliases=["sync"], help="Register exact source-controlled profile"
    )
    register.add_argument("--profile", default="TPLUS_ANALOG_CORE_EOD")
    register.add_argument("--version", type=int, default=1)
    register.add_argument("--config-hash")
    register.add_argument(
        "--apply", action="store_true", help="Write; omitted is dry-run"
    )
    history = analog_sub.add_parser("history", help="Build snapshot/outcome history")
    history_sub = history.add_subparsers(dest="history_command", required=True)
    build = history_sub.add_parser("build")
    build.add_argument("--profile", required=True)
    build.add_argument("--version", type=int, required=True)
    build.add_argument("--config-hash", required=True)
    build.add_argument("--symbols", nargs="+", required=True)
    build.add_argument("--from", dest="from_date", required=True)
    build.add_argument("--to", dest="to_date", required=True)
    build.add_argument(
        "--mode", choices=["full", "incremental", "replace"], required=True
    )
    build.add_argument("--apply", action="store_true")
    build.add_argument("--confirm-replace", action="store_true")
    validate = analog_sub.add_parser(
        "validate", help="Chronological calibration/validation/final evidence"
    )
    validate.add_argument("--profile", required=True)
    validate.add_argument("--version", type=int, required=True)
    validate.add_argument("--symbols", nargs="+", required=True)
    validate.add_argument("--from", dest="from_date", required=True)
    validate.add_argument("--to", dest="to_date", required=True)
    validate.add_argument(
        "--run-type", choices=["calibration", "validation", "final"], required=True
    )
    validate.add_argument("--thresholds", nargs="*", type=float)
    validate.add_argument("--final-test-start")
    validate.add_argument("--apply", action="store_true")
    for decision in ("approve", "reject"):
        review = analog_sub.add_parser(
            decision, help=f"Audit a manual {decision} decision"
        )
        review.add_argument("--profile", required=True)
        review.add_argument("--version", type=int, required=True)
        review.add_argument("--validation-run", required=True)
        review.add_argument("--reviewer", required=True)
        review.add_argument("--reason", required=True)
        review.add_argument("--apply", action="store_true")
    query = analog_sub.add_parser(
        "query", help="Persist an approved production analysis"
    )
    query.add_argument("--profile", required=True)
    query.add_argument("--version", type=int, required=True)
    query.add_argument("--symbol", required=True)
    query.add_argument("--date", required=True)
    query.add_argument("--checkpoint", default="EOD", choices=["EOD"])
    query.add_argument("--apply", action="store_true")
    inspect = analog_sub.add_parser(
        "inspect", help="Read source data and calculate research evidence without writes"
    )
    inspect.add_argument("--profile", required=True)
    inspect.add_argument("--version", type=int, required=True)
    inspect.add_argument("--symbol", required=True)
    inspect.add_argument("--date", required=True)
    inspect.add_argument("--checkpoint", default="EOD", choices=["EOD"])
    inspect.add_argument("--distance-threshold", type=float, required=True)
    daily_analog = analog_sub.add_parser(
        "daily", help="Separate idempotent EOD Analog runner"
    )
    daily_sub = daily_analog.add_subparsers(dest="daily_command", required=True)
    daily_run = daily_sub.add_parser("run")
    daily_run.add_argument("--profile", required=True)
    daily_run.add_argument("--version", type=int, required=True)
    daily_run.add_argument("--symbols", nargs="+", required=True)
    daily_run.add_argument("--date", required=True)
    daily_run.add_argument("--apply", action="store_true")
    return parser
