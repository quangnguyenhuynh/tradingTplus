# Trading T+ - Phase 1 Historical Analog Specification

Status: **design contract; not implemented**  
Supersedes: the fixed-rule / strategy-approval direction in this directory.

## Decision

Phase 1 does not begin from a buy/sell rule. At each supported checkpoint it
describes the current state of **one symbol**, finds comparable historical states
of that **same symbol**, and reports the observed H+ outcomes.

```text
time-safe feature state for SSI at 13:30
  -> versioned buckets and matching contract
  -> comparable historical SSI snapshots at 13:30
  -> H+1 / H+3 / H+5 outcome distribution
  -> read-only current analysis
```

No cross-symbol pooling is permitted in the core profile. SSI must never use HPG,
FPT, or another symbol's history to increase its sample size. If SSI does not
have enough comparable observations, return `insufficient_sample`.

## Time-safe input contract

- Checkpoints: 09:30, 11:30, 13:30, 14:30 Asia/Ho_Chi_Minh.
- Daily input uses only the prior completed trading session.
- Intraday input uses only closed 15m and 60m bars assembled from clean 1m
  `stock_intraday`; no partial candle.
- `stock_daily` is the trading-session axis and source for future close-based
  outcomes. Missing, stale, incomplete, suspended, or unsupported data is
  excluded; it is never fabricated as zero.
- Every snapshot records availability/lineage and profile identity so a
  look-ahead test can reproduce it.

## Matching profile

A profile is immutable by `profile_code + version + config_hash`. It declares
checkpoint(s), required feature dimensions, fixed/categorical or
training-period-only quantile buckets, missing/freshness rules, deterministic
fallback levels, same-symbol minimum effective sample, entry/cost/outcome model,
and chronological validation criteria.

A `group_key` is only a deterministic label for a bucketed state of one
symbol; it is not a cross-stock group. Fallback dimensions must be declared in
advance. The runtime may not tune boundaries or drop dimensions after seeing
outcomes.

## Evidence and validation

Historical snapshots are evaluated only after their H+ horizon is observable.
For each same-symbol match set, calculate sample/effective sample, probability
of positive return, return distribution, median/mean, downside quantiles,
MAE/MFE and any versioned target/stop result. Use observed trading sessions and
a fixed entry-price convention.

Validate chronologically: training choices precede validation/test periods, and
statistics available to a later snapshot use only earlier eligible evidence.
Compare against the same-symbol, same-checkpoint baseline. Approve/reject the
**profile method**, not a buy rule. Old strategy backtests and approvals are not
evidence for this method.

## Runtime and scope

At a checkpoint, runtime reads already-built features and approved historical
statistics, finds same-symbol matches, and writes at most an auditable analysis
record. It does not rerun the full backtest when a user opens the app.

Phase 1 output is analysis only: probability, return/risk distribution, sample
count, confidence and “not enough evidence” where applicable. Signal, alert,
portfolio %NAV, order execution, AI feature discovery, and cross-symbol models
are out of scope.

## Delivery order

1. Time-safe snapshot contract and tests.
2. Immutable profiles, same-symbol historical snapshots, outcomes, and stats.
3. Chronological out-of-sample validation and profile approval.
4. Read-only runtime lookup and audit record.

No Phase 1 command may automatically invoke ingest, feature computation, signal,
or alert generation. Existing legacy strategy/backtest artifacts remain dormant
for audit/reuse and must not be repurposed silently.
