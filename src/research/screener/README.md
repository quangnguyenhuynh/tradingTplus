# src/research/screener

RESEARCH_ACTIVE: unchanged Screener V1/V2 scores, configuration and methodology.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

Modules:

- `config.py`
- `rules.py`
- `rules_v2.py`
- `service.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.

---

# Stock Screener V1

Deterministic **research-only** EOD technical filter. No signal, trading decision,
probability, ranking, backtest, NAV allocation, or alerts.

## Sources and scope

- Reads `stock_features` only, exact Vietnam `trading_date` and `timeframe=1d`.
- The existing feature pipeline remains independent and is never run here.
- Uses only active master symbols; an explicit `--symbols` intersects that set.
- Does **not** silently use an earlier session when target-day features are missing.

## Rules (V1, provisional; not validated for profitability)

All five gates must pass:

1. Trend: `close > ema20 > ema50`.
2. RSI: `50 <= rsi14 <= 70`.
3. MACD: `macd_histogram > 0`.
4. Volume: `volume_ratio >= 1`.
5. Value: `value_ratio >= 1`.

`score` = 20 points per satisfied gate (0–100), **not** a probability.
If any required input is NULL, non-finite, or invalid, status is
`NOT_EVALUABLE` with `score=NULL` and an explicit list of missing/invalid fields.
Otherwise result is `PASS` or `FAIL`. All in-scope active symbols are reported.
A completely empty feature date fails rather than creating fabricated records.

## CLI

Read-only by default:

```bash
python main.py stock-screener --date 13/08/2026 --symbols SSI
```

Explicit persistence after applying `migrations/20261017_create_stock_screener_results.sql` manually:

```bash
python main.py stock-screener --date 13/08/2026 --symbols SSI --apply
```

Rerunning an exact `symbol + date + screener_version` upserts its result.
The table is service-role-only via RLS (no browser/client writes).
No automatic runner schedule, historical backfill, feature computation, or downstream stage is added.

## Limitations

Feature dates and coverage must be validated/backfilled separately. Old snapshots
are not proof of up-to-date signals. The screen is a cross-symbol candidate
filter; it does not pool different symbols for historical analog/outcome evidence.
Any rule threshold change needs a new version and independently documented testing.

## V2: versioned configuration and methodology

V1 remains unchanged and remains the default. V2 is an opt-in, research-only
weighted binary screener defined by:
- [JSON configuration](configs/v2.json), which the engine validates and executes.
- [English methodology](methodologies/v2.md).
- [Vietnamese methodology](methodologies/v2.vi.md).

Weights: trend 40, RSI 15, MACD 20, volume 10, value 15;
PASS at 70 of 100 points with complete valid inputs. Each rule earns its full
weight or zero. This is not a probability or a backtested model.
The JSON and both methodology documents are hashed together for version identity.

After manually applying `migrations/20261019_screener_v2_methodology.sql`,
review and register the immutable configuration once:

```bash
python main.py stock-screener-config --version v2 --language vi
python main.py stock-screener-config --version v2 --apply
python main.py stock-screener --date 13/08/2026 --symbols SSI --version v2
python main.py stock-screener --date 13/08/2026 --symbols SSI --version v2 --apply
```

Do not modify V2 JSON or its methodology after registration. Changes require a
new version and corresponding implementation. V2 results reference their
immutable config hash; V1 results retain a NULL config hash. No backtest,
signal, EOD ingest, or feature backfill is triggered by these commands.
