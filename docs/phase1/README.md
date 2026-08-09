# Phase 1 Research Docs

Phase 1 is the historical-analog research and method-validation layer after the
Phase 0 data/feature foundation.

## Active contract

| File | Status | Purpose |
| --- | --- | --- |
| [`HISTORICAL_ANALOG_SPEC.md`](HISTORICAL_ANALOG_SPEC.md) | Accepted design; not implemented | Same-symbol/same-checkpoint matching, H+ outcomes, validation, and runtime contract. |
| [`HISTORICAL_ANALOG_SPEC.vi.md`](HISTORICAL_ANALOG_SPEC.vi.md) | Accepted design; not implemented | Vietnamese version. |

The core rule is strict: SSI uses only historical SSI samples at the same
checkpoint. A group labels similar feature states; it never pools multiple
stocks. An inadequate same-symbol sample returns `insufficient_sample`.

```text
time-safe feature snapshot for one symbol
  -> same-symbol / same-checkpoint historical matches
  -> H+1 / H+3 / H+5 outcome distribution
  -> chronological validation
  -> read-only current analysis
```

Phase 1 produces research analysis, not a buy/sell signal, alert, ranking, or
%NAV recommendation.

## Superseded references

| File | Status |
| --- | --- |
| `RULE_BACKTEST_APPROVAL_SPEC.md` / `.vi.md` | Superseded fixed-rule design; audit only. |
| `CODEX_TASK_RULE_BACKTEST_APPROVAL.md` / `.vi.md` | Already-executed historical task; do not use for new work. |

The repository still contains executable fixed-rule strategy, signal, backtest,
CLI, schema, migration, and test artifacts. They are **implemented but dormant**.
Do not run their write paths, approve them for production, or use their metrics
as evidence for the active contract. They remain only for audit and deliberate
reuse until a separately approved cleanup task.

## Boundaries

- Ingest, validation, features, analog research, signal, and alert delivery stay
  separate.
- No Phase 1 command may invoke ingest or feature computation automatically.
- Historical-analog tables and CLI names in the active spec are proposals, not
  current executable behavior.
- Future implementation must start from the active spec and include migrations,
  backfill scope, leakage tests, and chronological out-of-sample evidence.

## Implemented EOD V1 core

The backend foundation for the narrower `TPLUS_ANALOG_CORE_EOD` V1 contract is
documented in [`../../src/analogs/README.md`](../../src/analogs/README.md). Its
threshold remains null/draft, so production results and approval are blocked.
