"""One-date EOD stock screener: explicit read-only preview and opt-in persistence."""
from __future__ import annotations

from typing import Any

from src.database.client import SupabaseClient
from src.features.stock.runtime import normalize_target_date, target_utc_bounds
from src.ingest.shared.symbol_scope import resolve_active_symbol_scope
from src.utils.time_utils import app_now_iso

from .rules import VERSION, evaluate
from .config import load_v2, assert_registered
from .rules_v2 import evaluate_v2

TABLE = "stock_screener_results"
PAGE_SIZE = 500
SELECT = (
    "symbol,time,last_updated_at,close,ema20,ema50,rsi14,"
    "macd_histogram,volume_ratio,value_ratio"
)


def _read_features(db: SupabaseClient, target_date) -> list[dict[str, Any]]:
    start, end, _ = target_utc_bounds(target_date)
    offset = 0
    rows: list[dict[str, Any]] = []
    last_page: tuple | None = None
    while True:
        query = (
            db.get().table("stock_features").select(SELECT)
            .eq("timeframe", "1d")
            .gte("time", start.isoformat())
            .lt("time", end.isoformat())
            .order("symbol").order("time")
            .range(offset, offset + PAGE_SIZE - 1)
        )
        result = db._with_retry(
            lambda q=query: q.execute(),
            action_name=f"read stock screener features date={target_date} offset={offset}",
        )
        page = result.data or []
        if not page:
            break
        identity = tuple((item.get("symbol"), item.get("time")) for item in page)
        if last_page == identity:
            raise RuntimeError("Repeated page reading stock_features for screener")
        last_page = identity
        rows.extend(page)
        offset += len(page)
    return rows


def _write_results(db: SupabaseClient, records: list[dict[str, Any]]) -> None:
    # Unique key is created by the required, manually applied migration.
    for offset in range(0, len(records), 200):
        chunk = records[offset:offset + 200]
        db._with_retry(
            lambda chunk=chunk: db.get().table(TABLE)
            .upsert(chunk, on_conflict="symbol,trading_date,screener_version")
            .execute(),
            action_name=f"write stock screener results [{offset}:{offset + len(chunk)}]",
        )


def run_stock_screener(
    trading_date: str,
    symbols: list[str] | None = None,
    apply: bool = False,
    db: SupabaseClient | None = None,
    version: str = VERSION,
) -> dict[str, Any]:
    """Evaluate an exact Vietnam trading date. Never triggers downstream stages."""
    if version not in ("v1", "v2"):
        raise ValueError("Unsupported screener version; select v1 or v2")
    profile = load_v2() if version == "v2" else None
    target = normalize_target_date(trading_date)
    client = db if db is not None else SupabaseClient()
    active, requested, ignored = resolve_active_symbol_scope(client, symbols)
    base = {
        "flow": "stock-screener",
        "date": target.isoformat(),
        "screener_version": version,
        "config_hash": profile["config_hash"] if profile else None,
        "mode": "apply" if apply else "preview",
        "requested_symbols": requested,
        "ignored_inactive_symbols": ignored,
    }
    if not active:
        return {**base, "status": "FAILED", "reason": "NO_ACTIVE_SYMBOLS", "evaluated": 0}

    rows = _read_features(client, target)
    if not rows:
        # Do not materialize fictitious NOT_EVALUABLE rows for an empty source date.
        return {**base, "status": "FAILED", "reason": "NO_FEATURE_DATA", "evaluated": 0}
    active_set = set(active)
    features: dict[str, dict] = {}
    for row in rows:
        symbol = row.get("symbol")
        if symbol not in active_set:
            continue
        if symbol in features:
            raise ValueError(f"More than one 1d feature for {symbol} on {target}")
        features[symbol] = row

    if not features:
        return {**base, "status": "FAILED", "reason": "NO_FEATURE_DATA_FOR_SCOPE", "evaluated": 0}

    stamp = app_now_iso()
    results: list[dict[str, Any]] = []
    for symbol in sorted(active):
        source = features.get(symbol)
        decision = evaluate_v2(source, profile["config"]) if profile else evaluate(source)
        results.append({
            "symbol": symbol,
            "trading_date": target.isoformat(),
            "screener_version": version,
            **({"config_hash": profile["config_hash"]} if profile else {}),
            "status": decision["status"],
            "score": decision["score"],
            "rule_results": decision["rule_results"],
            "missing_fields": decision["missing_fields"],
            "source_feature_time": source.get("time") if source else None,
            "source_feature_updated_at": source.get("last_updated_at") if source else None,
            "evaluated_at": stamp,
        })

    if apply:
        if profile:
            assert_registered(client, profile)
        _write_results(client, results)

    counts = {
        status: sum(item["status"] == status for item in results)
        for status in ("PASS", "FAIL", "NOT_EVALUABLE")
    }
    return {
        **base,
        "status": "PARTIAL" if counts["NOT_EVALUABLE"] else "OK",
        "evaluated": len(results),
        "counts": counts,
        "passed": [
            {"symbol": item["symbol"], "score": item["score"]}
            for item in results if item["status"] == "PASS"
        ],
        "not_evaluable_symbols": [
            item["symbol"] for item in results
            if item["status"] == "NOT_EVALUABLE"
        ][:20],
        "written": len(results) if apply else 0,
    }
