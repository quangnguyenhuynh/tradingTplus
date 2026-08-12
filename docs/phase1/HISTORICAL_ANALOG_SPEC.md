# Trading T+ - Phase 1 Historical Analog Specification

Status: **accepted contract; EOD V1 backend foundation implemented**

Reviewed: **2026-08-06**

Supersedes: the fixed-rule / strategy-approval direction in this directory.

## 1. Product question

At each supported checkpoint, Phase 1 answers one narrow question:

> Given the time-safe state of SSI now, how did SSI itself behave after
> comparable historical SSI states at the same checkpoint?

```text
time-safe SSI state at 13:30
  -> versioned matching profile
  -> comparable historical SSI states at 13:30
  -> H+1 / H+3 / H+5 outcome distribution
  -> read-only analysis with evidence and uncertainty
```

Phase 1 does not begin from a buy/sell rule and does not approve a fixed trading
strategy. It validates and approves the historical-analog **method**: feature
dimensions, transforms/buckets, matching, data-quality gates, entry/outcome
model, statistics, and validation criteria.

## 2. Non-negotiable same-symbol rule

- SSI current state is compared only with historical SSI states.
- HPG current state is compared only with historical HPG states.
- Historical candidates must use the same checkpoint as the current state.
- HPG, FPT, or any other symbol must never be added to SSI's sample.
- If SSI does not have enough eligible comparable observations, return
  `insufficient_sample`; never widen the search after seeing an outcome merely
  to make the sample look better.

A `group` or `group_key` is only a deterministic description of similar feature
states for one symbol. It never means a pool of different stocks. A future
cross-sectional or cross-symbol model would be a separate method, version,
validation report, and user-facing result; it is outside this specification.

## 3. Current implementation versus target

The superseded fixed-rule runtime, CLI, schema snapshot, specifications, and
tests were removed by the 2026-08-10 cleanup. Its two creation/enforcement
migrations remain only as immutable deployment history; a later cleanup
migration drops their retired tables when manually applied.

The implemented Historical Analog EOD V1 foundation provides the versioned
profile, snapshot/outcome, chronological validation, review, query evidence,
repository/service boundaries, and `analogs` CLI parser. The committed null
distance threshold and draft profile intentionally block final approval and
production queries. Intraday checkpoints remain outside the implemented EOD V1
scope.

## 4. Scope

Phase 1 includes:

- time-safe snapshots at 09:30, 11:30, 13:30, and 14:30;
- same-symbol/same-checkpoint historical matching;
- H+1/H+3/H+5 outcomes and risk distributions;
- chronological out-of-sample validation;
- versioned method approval;
- read-only current analysis with an optional audit record.

Phase 1 excludes:

- buy/sell signals, alerts, ranking, and cooldown rules;
- portfolio construction, %NAV, correlation, and position limits;
- order execution, fees outside the versioned research cost model, and broker
  integration;
- AI/ML feature discovery or automatic parameter search;
- cross-symbol sample pooling;
- automatic execution after ingest or feature computation.

## 5. Data sources and provenance

| Source | Role |
| --- | --- |
| `features`, timeframe `1d` | Prior completed session trend, momentum, and liquidity context. |
| `features`, timeframes `15m`/`60m` | Closed intraday state available by the checkpoint. |
| `stock_intraday`, timeframe `1m` | Candidate entry price and availability checks after the checkpoint. |
| `stock_daily` | Observed trading-session axis and H+ close/high/low outcomes. |
| Completeness/validation evidence | Exclude ineligible symbol-session-timeframe observations. |

Phase 0 contracts remain authoritative:

- `1d` features come only from `stock_daily`;
- `15m`/`60m` features are aggregated from clean 1m `stock_intraday`;
- missing data is not converted to zero;
- no synthetic weekend, holiday, empty-response, or unsupported-endpoint rows;
- the analog pipeline remains separate from ingest and feature computation.

Market and sector context may be included as feature dimensions when their
source and point-in-time availability are verified. Even then, the historical
outcome set for SSI still contains SSI observations only.

## 6. Time and look-ahead contract

- Interpret checkpoints in `Asia/Ho_Chi_Minh`; keep stored timestamps
  timezone-aware.
- A current session `E` uses daily features from the latest completed session
  before `E`, normally `D`.
- Intraday features are eligible only when their candle is closed and its
  `available_at <= checkpoint_time`.
- `features.time` is a bucket start under the current feature contract, not proof
  that the bucket was already available.
- A 15m row starting at 09:30 is unavailable at 09:30 and first eligible at
  09:45. A 60m row starting at 09:00 is unavailable at 09:30.
- Session edges and the lunch break must be handled explicitly; aggregation may
  not cross trading dates or the lunch break.
- Every required dimension declares a freshness limit. Missing or stale input
  produces `not_evaluable`, not an arbitrary older substitute.

Each snapshot must preserve enough lineage to reproduce the decision:

- symbol, trading session, checkpoint, and decision time;
- feature timeframe, bucket start, `available_at`, and value used;
- profile code/version/hash;
- data-quality and exclusion reasons;
- a data/version identity or equivalent source fingerprint.

## 7. Snapshot and matching profile

A logical snapshot contains:

```json
{
  "symbol": "SSI",
  "session": "2026-08-06",
  "checkpoint": "13:30",
  "decision_time": "2026-08-06T13:30:00+07:00",
  "profile": {"code": "TPLUS_ANALOG_CORE", "version": 1, "hash": "..."},
  "status": "evaluable",
  "feature_values": {},
  "bucket_labels": {},
  "group_key": "...",
  "input_refs": [],
  "data_quality": {}
}
```

Minimum statuses:

| Status | Meaning |
| --- | --- |
| `evaluable` | All required time-safe inputs pass data-quality gates. |
| `not_evaluable` | Required input is missing/stale/incomplete or no valid entry exists. |
| `excluded` | The symbol-session fails a versioned eligibility or completeness rule. |
| `insufficient_sample` | Current snapshot is valid, but its same-symbol match set is too small or unreliable. |

A profile is immutable by `profile_code + version + config_hash` and declares:

- supported checkpoints;
- required/optional dimensions and source timeframes;
- transforms and fixed/categorical or training-only quantile buckets;
- missing and freshness rules;
- predeclared matching/fallback levels;
- same-symbol minimum raw/effective sample rules;
- entry, cost, outcome, and holding-horizon models;
- chronological split and acceptance criteria.

Bucket boundaries may not adapt to the current snapshot or its future outcome.
Fallback may remove only dimensions declared in advance. If every level fails
the sample rule, the result is `insufficient_sample`.

## 8. Historical build and outcomes

For every eligible `symbol + session + checkpoint`:

1. Resolve observed trading sessions using the versioned calendar contract.
2. Apply completeness and eligibility before snapshot creation.
3. Use the prior completed daily feature state.
4. Use only fresh intraday features already closed at the checkpoint.
5. Create deterministic bucket labels and group key.
6. Resolve entry using a fixed, versioned convention.
7. Calculate H+1/H+3/H+5 outcomes over observed trading sessions.
8. Preserve missing/exclusion reasons instead of filling data.

The initial proposed entry model is `next_tradable_1m_open_v1`: the first valid
clean 1m open strictly after the decision time in the same session. A missing
entry is excluded from the denominator and reported.

For horizon H+N, gross return is `close_HN / entry_price - 1`; net return applies
the versioned fee, tax, and slippage assumptions. MFE/MAE, target-before-stop,
and other path metrics may be calculated only from eligible observations inside
the exact holding window.

The build must eventually support full history, incremental updates, and exact
scoped replacement. Writes must be idempotent or immutable by data/profile
identity; stale child outcomes must never survive a rebuild.

## 9. Statistics and baseline

For each `symbol + profile + checkpoint + group + matching level + horizon`,
report at least:

- raw and usable sample counts, missing count, distinct trading sessions, and
  effective sample size;
- probability of positive net return;
- versioned target/loss probabilities;
- mean, median, and relevant quantiles;
- downside risk and MFE/MAE where eligible;
- a confidence interval, initially Wilson for binomial probabilities;
- the same-symbol, same-checkpoint unconditional baseline over the eligible
  comparison period;
- lift/difference from that baseline;
- training/validation/test periods and profile/data identity.

Never present a probability without its sample size and uncertainty. Baseline
also remains symbol-specific: SSI analog evidence is compared with the eligible
SSI baseline, not a market-wide stock pool.

## 10. Validation and approval

Do not random-split time series. Use chronological training, validation, and
final-test periods; add walk-forward evaluation where practical. Training-only
quantile buckets are fitted on training data and frozen thereafter. Evidence
available for a historical prediction may use only earlier eligible records.

Required evidence includes:

- explicit look-ahead tests around every checkpoint and candle boundary;
- exclusions and completeness reasons;
- raw/effective sample by symbol, checkpoint, horizon, and time period;
- calibration, Brier score or an equivalent probability metric;
- lift over the same-symbol baseline;
- stability across time and documented market regimes;
- H+1/H+3/H+5 return and risk distributions;
- entry/cost/outcome assumptions and missing counts;
- profile hash, data identity, and code commit.

Approve/reject the exact method identity, not a current state or buy rule.
Changing a dimension, bucket, fallback, checkpoint, freshness rule, feature
formula, entry/cost/outcome model, or acceptance criterion requires a new
version and new evidence.

## 11. Runtime response

Opening the app does not rerun historical validation. Runtime:

1. resolves `symbol + session + checkpoint`;
2. loads an approved profile version;
3. assembles a time-safe current snapshot;
4. returns `not_evaluable` when required inputs fail;
5. matches only prior snapshots of that symbol and checkpoint;
6. returns `insufficient_sample` when the predeclared sample rule fails;
7. otherwise returns probabilities, return/risk distribution, sample,
   confidence interval, same-symbol baseline, assumptions, and explanation;
8. may write an audit analysis record, but no Phase 1 signal.

## 12. Proposed implementation contracts

Names below are proposals and must be rechecked against the schema and CLI
parser in the implementation task:

| Proposed table | Purpose |
| --- | --- |
| `analog_profiles` | Immutable method metadata/configuration and lifecycle. |
| `analog_snapshots` | Historical/current time-safe state and lineage. |
| `analog_outcomes` | Entry and H+ outcomes for each snapshot. |
| `analog_validation_runs` | Chronological evidence and metrics. |
| `analog_group_stats` | Same-symbol group statistics by checkpoint/horizon. |
| `analog_profile_reviews` | Audited approve/reject decision. |
| `analog_queries` | Optional runtime-analysis audit; not a signal. |

Illustrative CLI only:

```bash
python main.py analogs history build --profile TPLUS_ANALOG_CORE --version 1 --from 01/01/2021 --to 31/07/2026 --symbols SSI
python main.py analogs validate --profile TPLUS_ANALOG_CORE --version 1 --symbols SSI
python main.py analogs query --profile TPLUS_ANALOG_CORE --version 1 --symbol SSI --date 06/08/2026 --checkpoint 13:30
```

These commands do not exist yet. No command may automatically invoke ingest,
feature computation, signal, alert, or portfolio logic.

## 13. Implementation tests and acceptance

Implementation is not complete until tests prove:

- closed-bucket availability at 09:30/09:45, 11:30, 13:30, and 14:30;
- prior-session daily input and no current-session daily leakage;
- strict same-symbol and same-checkpoint matching;
- no cross-symbol outcome can enter the sample or baseline;
- deterministic profile hash, buckets, group key, and fallback order;
- missing/stale input returns `not_evaluable`;
- inadequate samples return `insufficient_sample` without probability;
- H+ session mapping handles weekends/holidays through observed-session rules;
- denominators, confidence intervals, baseline, and lift are correct;
- full/incremental/scoped-replace builds do not leave stale outcomes;
- runtime never creates a signal, alert, or %NAV recommendation.

Run targeted tests first, then the full offline suite, compileall, and CLI help.
SSI/Supabase smoke tests remain read-only unless an exact write scope is
explicitly approved.

## 14. Delivery order

1. Time-safe snapshot contract and leakage tests.
2. Immutable profiles, same-symbol snapshots, outcomes, and build modes.
3. Chronological out-of-sample validation and profile approval.
4. Read-only runtime lookup and optional audit record.

Each item should be a separate task/PR. Schema changes require migrations.

## 15. Documentation-task database impact

- Migration: none.
- Database rows: none.
- Market-data or feature backfill: none.
- Future implementation will require a separately reviewed schema/migration and
  scoped historical build for analog snapshots/outcomes.

### Implemented V1 runtime boundary (EOD only)

The current V1 runtime persists EOD snapshots from `features.timeframe='1d'` and observed-session H+1/H+3/H+5 outcomes from `stock_daily`. Production queries read that persisted evidence; audit persistence is gated by exact approval and a numeric frozen threshold. The source profile remains draft/null-threshold. The inspect command is a read-only, in-memory research/debug path with an explicit ephemeral threshold. Intraday checkpoints, signals, rankings, alerts, portfolio sizing, and backtest rules are not part of this V1 runtime.
