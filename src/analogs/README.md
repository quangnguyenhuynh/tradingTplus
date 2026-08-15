# Historical Analog Core EOD V1 and V2

`TPLUS_ANALOG_CORE_EOD` describes one symbol's verified **1d EOD** state and
compares it only with earlier states of that same symbol. It is historical
analysis, not a trading backtest: it has no orders, entry price, costs, signals,
alerts, stop/target, portfolio drawdown, or NAV sizing.

## Objects and units

A **snapshot** is the nine-dimensional state at session D. An **outcome** is one
future observation, `close[H] / close[D] - 1`, at verified trading sessions.
V1 uses H+1/H+3/H+5; V2 adds H+10. A **validation result** is chronological evidence about the
method; it is not a runtime query. Ratios use decimal units (`0.043` = 4.3%).

| Dimension | Formula | Weight |
|---|---|---:|
| `return_5d` | `close[D]/close[D-5 sessions]-1` | .10 |
| `price_vs_ema20_pct` | `close/ema20-1` | .15 |
| `ema20_vs_ema50_pct` | `ema20/ema50-1` | .15 |
| `rsi14` | verified feature, 0–100 | .10 |
| `macd_histogram_pct` | `macd_histogram/close` | .10 |
| `distance_to_high20_pct` | `close/high_20_bars-1` | .15 |
| `volume_ratio` | verified feature ratio | .075 |
| `value_ratio` | verified feature ratio | .075 |
| `close_position_in_candle` | `(close-low)/(high-low)` | .10 |

Missing/non-finite inputs, zero denominators, fewer than five earlier sessions,
and zero-range candles are never converted to zero; they make a snapshot
`not_evaluable` with reason codes.

## Immutable lifecycle and matching

The complete JSON configuration is canonically serialized and SHA-256 hashed.
The database registry supports `draft`, `validated`, `approved`, `rejected`, and
`retired`. Approval is manual and must cite an exact completed `final` run for
the same hash. Any contract change requires a new version after final evidence.

For D, eligible candidates have identical profile/version/hash, `1d`, `EOD`,
symbol, acceptable status, are earlier than D and within five years, and have
all outcomes observable by D. Median and IQR are fit only on that eligible past.
Zero IQR is `not_evaluable`. Weighted Euclidean distance is transformed to
`exp(-distance)*100`; similarity is proximity, not positive probability. All eligible rows are ranked deterministically and the nearest configured
`top_k` (30 by default) are retained; `distance_threshold` is not an input
filter. Fewer than `top_k` returns `insufficient_sample`, without padding.

A completed result reports positive probability (`return > 0`), median, P25,
Wilson interval, same-symbol baseline, and lift (probability minus baseline).
The query, normalization parameters, and exact ranked matches are immutable
audit evidence.

## Calibration and validation

Radius calibration runs walk-forward within its declared training interval. It neither edits nor approves a profile and cannot qualify as final
evidence. Walk-forward fitting and matching use only data observable before
each simulated D; the current/future outcome is used later only for scoring.
Random splitting is forbidden. Reports include coverage, insufficient counts,
Brier/baseline Brier, calibration buckets, lift, median-return error, yearly
stability, and invalid reasons.

`analog_quality` reports sample size, `top_k`, dynamic neighbour radius `d_k`
(`d30` by default), median and p90 distances, and a walk-forward radius
percentile. P50/P75/P95 define `good`, `usable`, `weak`, and
`out_of_distribution`; insufficient calibration returns `unknown`, never a fake
percentile. Weak/OOD results retain T+ statistics with a warning. Radius quality
is similarity, not forecast probability; Wilson intervals remain separate under
`statistical_confidence`.

## Build and operations

- `full`: scoped non-destructive upsert.
- `incremental`: scoped watermark/new-and-affected upsert.
- `replace`: deletes only exact profile/hash, symbols, and dates; `--apply` and
  `--confirm-replace` are both required.
- All writes are dry-run unless `--apply` is supplied and all modes are
  idempotent on migration uniqueness keys.

Commands:

```bash
python main.py analogs profiles list
python main.py analogs profiles register --profile TPLUS_ANALOG_CORE_EOD --version 2 [--apply]
python main.py analogs history build --profile TPLUS_ANALOG_CORE_EOD --version 1 --config-hash HASH --symbols SSI --from 01/01/2021 --to 31/07/2026 --mode full [--apply]
python main.py analogs validate --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbols SSI --from 01/01/2021 --to 31/12/2024 --run-type calibration --final-test-start 01/01/2025 [--apply]
python main.py analogs approve --profile TPLUS_ANALOG_CORE_EOD --version 1 --validation-run UUID --reviewer NAME --reason TEXT [--apply]
python main.py analogs reject --profile TPLUS_ANALOG_CORE_EOD --version 1 --validation-run UUID --reviewer NAME --reason TEXT [--apply]
python main.py analogs query --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbol SSI --date 07/08/2026 [--apply]
python main.py analogs daily run --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbols SSI --date 07/08/2026 [--apply]
```

Operational order is: verified 1d features → snapshots → older outcomes →
approved queries. No Analog command invokes ingest, features, signals, backtests,
or alerts. Apply the migration manually, register the profile, and build an
explicit scope. Existing features need no backfill; snapshot/outcome history
does.

Tables: `analog_profiles` owns configuration/lifecycle;
`analog_snapshots` owns state/lineage; `analog_outcomes` owns one H row;
`analog_validation_runs` owns chronological evidence;
`analog_profile_reviews` owns human decisions; `analog_queries` owns persisted
results; `analog_query_matches` owns exact explanations. Mobile roles have no
writes.

No HTTP framework exists in this repository. `AnalogReadService` supplies the
future read contracts for `GET /analog-profiles/{code}/{version}`, `GET
/analogs/{symbol}/latest?checkpoint=EOD`, and `GET /analog-queries/{id}`; endpoint
wiring is deferred and GET must never recompute analysis.

Common reasons include `EXACT_PROFILE_NOT_APPROVED`,
`INSUFFICIENT_FIVE_SESSION_HISTORY`, `MISSING_*`, `NON_FINITE_*`,
`ZERO_DENOMINATOR_*`, `ZERO_CANDLE_RANGE`, `ZERO_OR_INVALID_IQR:*`,
`TARGET_SESSION_NOT_YET_OBSERVABLE`, and `VERIFIED_SESSION_PRICE_MISSING`.
Phase 1 excludes intraday inputs, cross-symbol pooling, SSI calls, recommendations,
execution/P&L, alerts, ranking, and NAV.

## Production runtime commands

V1 is EOD/`1d` only. `analogs profiles register` is a dry run unless `--apply`; list and applied registration use `analog_profiles` and require the exact source-controlled identity. `analogs history build` reads paginated `features` 1d and `stock_daily`, and only `--apply` upserts snapshots plus H+1/H+3/H+5 outcomes. Replace additionally requires `--confirm-replace` and is limited to the exact identity/symbol/date/EOD scope.

V2 keeps the same dimensions and matching contract and adds H+10 as a fourth
`analog_outcomes` row (`horizon_sessions=10`), never as a column. Exact profile
resolution requires code/version and optionally verifies the source config hash;
it never substitutes the latest version. V2 remains draft and needs
its own history build and chronological validation, and cannot reuse V1 evidence.

`analogs query` reads persisted snapshot/outcome evidence. Without `--apply` it is read-only; with `--apply` it may atomically audit an exact approved profile for an exact approved profile. V1 remains draft, so production query is blocked by `EXACT_PROFILE_NOT_APPROVED`.

`analogs inspect --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbol SSI --date DD/MM/YYYY --checkpoint EOD --distance-threshold 0.5` reads source data and calculates entirely in memory. It never writes an Analog table. The legacy threshold option is ignored and retained only for CLI compatibility.
