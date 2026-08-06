# Phase 1 Research Docs

Phase 1 starts the new downstream research layer after Phase 0 data and feature
verification. These documents are design contracts, not executable behavior.

## Documents

| File | Purpose |
| --- | --- |
| `RULE_BACKTEST_APPROVAL_SPEC.md` | Minimal contract for designing a two-step T+ rule, replaying it in backtests, and approving a rule version before live signal scans. |
| `RULE_BACKTEST_APPROVAL_SPEC.vi.md` | Vietnamese version of the rule/backtest/approval contract. |
| `CODEX_TASK_RULE_BACKTEST_APPROVAL.md` | Self-contained Codex task for implementing the rule/backtest approval framework. |
| `CODEX_TASK_RULE_BACKTEST_APPROVAL.vi.md` | Vietnamese version of the Codex task. |

## Scope

Phase 1 rule work must stay downstream of the existing `features` pipeline:

```text
features
  -> two-step rule replay
  -> backtest evidence
  -> strategy approval
  -> approved-rule live signal scan
```

Ingest, validation, clean market data, and feature computation remain separate.
Do not restore the retired legacy signal/backtest tables or code.

### Operational Phase 1 CLI (2026-08-06)
The database-backed commands are executable and remain separate from ingest/features. Dry-run is the default; `--write` is explicit. Production setup/signal writes require the exact approved strategy version/config. Historical sessions come from observed `stock_daily`; live setup requires an explicit target session. First-match uniqueness permits only one signal per strategy/config/symbol/session. Rule/evaluator changes require a new version and new evidence.
