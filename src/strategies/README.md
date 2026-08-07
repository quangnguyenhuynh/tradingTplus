# Strategies - dormant fixed-rule research

Current code implements immutable two-stage `BREAKOUT_V1` and `PULLBACK_V1`
rules with auditable `RuleDecision` values. It is executable legacy research,
not the accepted Phase 1 production design.

Do not add strategies, approve these rules for production, run write paths, or
use their backtest metrics as historical-analog evidence. Keep the package for
audit and deliberate reuse until a separate cleanup task. New Phase 1 work must
follow the [same-symbol historical-analog specification](../../docs/phase1/HISTORICAL_ANALOG_SPEC.md).
