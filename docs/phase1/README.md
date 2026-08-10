# Phase 1

## Active contract

Historical Analog is the only active Phase 1 direction. The EOD V1 backend
foundation is implemented; the committed profile remains draft with a null
distance threshold, so final validation, approval, and production queries stay
blocked.

- [English specification](HISTORICAL_ANALOG_SPEC.md)
- [Vietnamese specification](HISTORICAL_ANALOG_SPEC.vi.md)
- [Implemented package](../../src/analogs/README.md)
- [Database migration](../../migrations/20260809_create_historical_analog_core_eod_v1.sql)

The superseded fixed-rule specifications and executable artifacts were removed
by the 2026-08-10 cleanup. Historical migration files remain as deployment
history and the cleanup migration removes their six retired tables when applied.

## Boundaries

Phase 1 compares only the same symbol with eligible prior history at the same
checkpoint. It never widens an insufficient sample across symbols. Ingest and
feature commands do not invoke Analog analysis, signals, alerts, ranking, NAV,
or execution.
