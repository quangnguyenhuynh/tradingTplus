# SSI v3 repository restructuring — final report

## 1. Overall result: PARTIAL

The requested local restructuring is implemented and offline verification passes. Full completion is not claimed: PostgreSQL-backed tests could not run locally and live SSI/Supabase integrations were not exercised. The connected GitHub API confirms current remote dev matches the checkout base commit `90a57b1`. No production writes were attempted. Changes remain in the working tree and the supplied patch; no branch was pushed or deployment performed.

## 2. Completed stages

- A: audited local checkout, entrypoints, provider/canonical/persistence boundaries, schema/migrations, workflows, tests and docs; baseline passed. The GitHub branch endpoint later verified remote dev at the exact checkout base SHA.
- B: removed v2 REST client, adapter, mapping, fallback selection, credentials and classic SignalR connection; disabled legacy-dependent and combined operations before I/O.
- C: moved verified v3 provider and canonical contracts into isolated boundaries. AdapterResult carries raw provenance, keeping service logic independent of endpoint versions.
- D: reorganized daily/index ingest, shared/workflow/maintenance logic and quality. Retained pure historical models/validators/persistence helpers; disabled unsupported ingest. Index preview now uses v3 without DB construction.
- E: moved stock/foreign/index features and screener/analogs; formulas/configurations/profile assets preserved.
- F: split parser and handlers, made main.py thin, reorganized scripts, preserved active CLI arguments, updated workflow paths and retired credentials/scheduling.
- G: bilingual package guides, root/current-state/CLI/architecture docs, historical retirement notes, regression and structural checks completed locally.

## 3. File mapping

The exact machine-readable inventory is `RESTRUCTURE_MAPPING.json`. `[]` means retired without an executable replacement. A split can have multiple destination paths. All original changed/moved paths are included below; new files are listed separately.

| Old path | New path(s) |
| --- | --- |
| `.env.example` | `.env.example` |
| `.github/workflows/README.md` | `.github/workflows/README.md` |
| `.github/workflows/README.vi.md` | `.github/workflows/README.vi.md` |
| `.github/workflows/index-eod-v2.yml` | `.github/workflows/index-eod-v2.yml` |
| `.github/workflows/stock-eod.yml` | `.github/workflows/stock-eod.yml` |
| `.github/workflows/stock-intraday.yml` | `.github/workflows/stock-intraday.yml` |
| `README.md` | `README.md` |
| `README.vi.md` | `README.vi.md` |
| `docs/ARCHITECTURE_DECISIONS.md` | `docs/ARCHITECTURE_DECISIONS.md` |
| `docs/CLI_USAGE.md` | `docs/CLI_USAGE.md` |
| `docs/CLI_USAGE.vi.md` | `docs/CLI_USAGE.vi.md` |
| `docs/CURRENT_STATE.md` | `docs/CURRENT_STATE.md` |
| `docs/DATA_PIPELINE.md` | `docs/DATA_PIPELINE.md` |
| `docs/PROJECT_OVERVIEW.md` | `docs/PROJECT_OVERVIEW.md` |
| `docs/README.md` | `docs/README.md` |
| `docs/README.vi.md` | `docs/README.vi.md` |
| `docs/STOCK_EOD_PIPELINE.md` | `docs/STOCK_EOD_PIPELINE.md` |
| `docs/STOCK_EOD_PIPELINE.vi.md` | `docs/STOCK_EOD_PIPELINE.vi.md` |
| `docs/STOCK_INTRADAY_PIPELINE.md` | `docs/STOCK_INTRADAY_PIPELINE.md` |
| `docs/STOCK_INTRADAY_PIPELINE.vi.md` | `docs/STOCK_INTRADAY_PIPELINE.vi.md` |
| `docs/phase0/PHASE0_VALIDATION_REPORT.md` | `docs/phase0/PHASE0_VALIDATION_REPORT.md` |
| `docs/phase0/PHASE0_VALIDATION_REPORT.vi.md` | `docs/phase0/PHASE0_VALIDATION_REPORT.vi.md` |
| `docs/phase1/README.md` | `docs/phase1/README.md` |
| `docs/phase1/README.vi.md` | `docs/phase1/README.vi.md` |
| `main.py` | `main.py`, `src/cli/__init__.py`, `src/cli/analogs.py`, `src/cli/common.py`, `src/cli/features.py`, `src/cli/foreign.py`, `src/cli/index.py`, `src/cli/maintenance.py`, `src/cli/parser.py`, `src/cli/screener.py`, `src/cli/stock.py`, `src/cli/streaming.py` |
| `requirements.txt` | `requirements.txt` |
| `scripts/README.md` | `scripts/README.md` |
| `scripts/README.vi.md` | `scripts/README.vi.md` |
| `scripts/backfill_stock_intraday_value.sql` | `scripts/maintenance/backfill_stock_intraday_value.sql` |
| `scripts/check_complete_ssi_ingest.py` | `scripts/checks/check_complete_ssi_ingest.py` |
| `scripts/check_ingest.py` | `scripts/checks/check_ingest.py` |
| `scripts/check_ssi_ingest_schema.py` | `scripts/checks/check_ssi_ingest_schema.py` |
| `scripts/check_supabase.py` | `scripts/checks/check_supabase.py` |
| `scripts/eod_dry_run.py` | `scripts/previews/eod_dry_run.py` |
| `scripts/fetch_one_day.py` | `scripts/maintenance/fetch_one_day.py` |
| `scripts/phase0_reconcile_sample.py` | `scripts/checks/phase0_reconcile_sample.py` |
| `scripts/phase0_validate_schema.py` | `scripts/checks/phase0_validate_schema.py` |
| `scripts/run_features.py` | `scripts/previews/run_features.py` |
| `scripts/snapshot_orderbook.py` | `scripts/capture/snapshot_orderbook.py` |
| `scripts/snapshot_stream.py` | `scripts/capture/snapshot_stream.py` |
| `scripts/ssi_api_inspector/README.md` | `scripts/inspectors/ssi_rest/README.md` |
| `scripts/ssi_api_inspector/README.vi.md` | `scripts/inspectors/ssi_rest/README.vi.md` |
| `scripts/ssi_api_inspector/__init__.py` | `scripts/inspectors/ssi_rest/__init__.py` |
| `scripts/ssi_api_inspector/client.py` | `scripts/inspectors/ssi_rest/client.py` |
| `scripts/ssi_api_inspector/datasets.py` | `scripts/inspectors/ssi_rest/datasets.py` |
| `scripts/ssi_api_inspector/endpoints.py` | `scripts/inspectors/ssi_rest/endpoints.py` |
| `scripts/ssi_api_inspector/inspect.py` | `scripts/inspectors/ssi_rest/inspect.py` |
| `scripts/ssi_api_inspector/mapping.py` | `scripts/inspectors/ssi_rest/mapping.py` |
| `scripts/ssi_streaming_inspector/README.md` | `scripts/inspectors/ssi_streaming/README.md` |
| `scripts/ssi_streaming_inspector/README.vi.md` | `scripts/inspectors/ssi_streaming/README.vi.md` |
| `scripts/ssi_streaming_inspector/__init__.py` | `scripts/inspectors/ssi_streaming/__init__.py` |
| `scripts/ssi_streaming_inspector/inspect.py` | `scripts/inspectors/ssi_streaming/inspect.py` |
| `scripts/ssi_streaming_inspector/output.py` | `scripts/inspectors/ssi_streaming/output.py` |
| `scripts/ssi_streaming_inspector/registry.py` | `scripts/inspectors/ssi_streaming/registry.py` |
| `src/README.md` | `src/README.md` |
| `src/README.vi.md` | `src/README.vi.md` |
| `src/analogs/README.md` | `src/research/analogs/README.md` |
| `src/analogs/README.vi.md` | `src/research/analogs/README.vi.md` |
| `src/analogs/__init__.py` | `src/research/analogs/__init__.py` |
| `src/analogs/cli.py` | `src/research/analogs/cli.py` |
| `src/analogs/core.py` | `src/research/analogs/core.py` |
| `src/analogs/pipeline.py` | `src/research/analogs/pipeline.py` |
| `src/analogs/profile.py` | `src/research/analogs/profile.py` |
| `src/analogs/profiles/tplus_analog_core_eod_v1.json` | `src/research/analogs/profiles/tplus_analog_core_eod_v1.json` |
| `src/analogs/profiles/tplus_analog_core_eod_v2.json` | `src/research/analogs/profiles/tplus_analog_core_eod_v2.json` |
| `src/analogs/repository.py` | `src/research/analogs/repository.py` |
| `src/analogs/runtime.py` | `src/research/analogs/runtime.py` |
| `src/analogs/service.py` | `src/research/analogs/service.py` |
| `src/analogs/validation.py` | `src/research/analogs/validation.py` |
| `src/config.py` | `src/config.py` |
| `src/data_contracts/README.md` | `src/contracts/README.md` |
| `src/data_contracts/README.vi.md` | `src/contracts/README.vi.md` |
| `src/data_contracts/__init__.py` | `src/contracts/__init__.py` |
| `src/data_contracts/definitions.json` | `src/contracts/definitions.json` |
| `src/data_contracts/derived.py` | `src/contracts/derived.py` |
| `src/data_contracts/engine.py` | `src/contracts/engine.py` |
| `src/data_contracts/mappings/ssi_v2.json` | RETIRED |
| `src/data_contracts/mappings/ssi_v3.json` | `src/contracts/mappings/ssi_v3.json` |
| `src/data_contracts/registry.py` | `src/contracts/registry.py` |
| `src/data_contracts/transforms.py` | `src/contracts/transforms.py` |
| `src/data_sources/__init__.py` | RETIRED |
| `src/data_sources/base.py` | `src/providers/ssi/base.py` |
| `src/data_sources/registry.py` | `src/providers/ssi/registry.py` |
| `src/data_sources/ssi_v2.py` | RETIRED |
| `src/data_sources/ssi_v3.py` | `src/providers/ssi/adapters/v3.py` |
| `src/database/README.md` | `src/database/README.md` |
| `src/database/README.vi.md` | `src/database/README.vi.md` |
| `src/engine/README.md` | RETIRED |
| `src/engine/README.vi.md` | RETIRED |
| `src/engine/__init__.py` | RETIRED |
| `src/engine/data_quality.py` | RETIRED |
| `src/features/README.md` | `src/features/stock/README.md` |
| `src/features/README.vi.md` | `src/features/stock/README.vi.md` |
| `src/features/__init__.py` | `src/features/__init__.py`, `src/features/stock/__init__.py` |
| `src/features/backfill.py` | `src/features/stock/backfill.py` |
| `src/features/common.py` | `src/features/stock/common.py` |
| `src/features/daily.py` | `src/features/stock/daily.py` |
| `src/features/intraday.py` | `src/features/stock/intraday.py` |
| `src/features/policy.py` | `src/features/stock/policy.py` |
| `src/features/runner.py` | `src/features/stock/runner.py` |
| `src/features/runtime.py` | `src/features/stock/runtime.py` |
| `src/foreign_features/README.md` | `src/features/foreign/README.md` |
| `src/foreign_features/README.vi.md` | `src/features/foreign/README.vi.md` |
| `src/foreign_features/__init__.py` | `src/features/foreign/__init__.py` |
| `src/foreign_features/calculator.py` | `src/features/foreign/calculator.py` |
| `src/foreign_features/calendar.py` | `src/features/foreign/calendar.py` |
| `src/foreign_features/loader.py` | `src/features/foreign/loader.py` |
| `src/foreign_features/persistence.py` | `src/features/foreign/persistence.py` |
| `src/foreign_features/service.py` | `src/features/foreign/service.py` |
| `src/foreign_features/validator.py` | `src/features/foreign/validator.py` |
| `src/index_features/README.md` | `src/features/index/README.md` |
| `src/index_features/README.vi.md` | `src/features/index/README.vi.md` |
| `src/index_features/__init__.py` | `src/features/index/__init__.py` |
| `src/index_features/calculator.py` | `src/features/index/calculator.py` |
| `src/index_features/completeness.py` | `src/features/index/completeness.py` |
| `src/index_features/pipeline.py` | `src/features/index/pipeline.py` |
| `src/index_features/repository.py` | `src/features/index/repository.py` |
| `src/pipeline/README.md` | `src/ingest/README.md` |
| `src/pipeline/README.vi.md` | `src/ingest/README.vi.md` |
| `src/pipeline/__init__.py` | `src/ingest/__init__.py` |
| `src/pipeline/backfill.py` | `src/ingest/maintenance/backfill.py` |
| `src/pipeline/daily.py` | `src/ingest/stock_daily/daily.py` |
| `src/pipeline/daily_fetcher.py` | `src/ingest/stock_daily/daily_fetcher.py` |
| `src/pipeline/daily_mapper.py` | `src/ingest/stock_daily/daily_mapper.py` |
| `src/pipeline/daily_persistence.py` | `src/ingest/stock_daily/daily_persistence.py` |
| `src/pipeline/daily_service.py` | `src/ingest/stock_daily/daily_service.py` |
| `src/pipeline/date_utils.py` | `src/ingest/shared/date_utils.py` |
| `src/pipeline/eod_dry_run.py` | `src/diagnostics/eod_dry_run.py` |
| `src/pipeline/fetch_one_day.py` | `src/diagnostics/fetch_one_day.py` |
| `src/pipeline/index_backfill.py` | `src/ingest/index_daily/index_backfill.py` |
| `src/pipeline/index_completeness.py` | `src/quality/completeness/index_completeness.py` |
| `src/pipeline/index_daily.py` | `src/ingest/index_daily/index_daily.py` |
| `src/pipeline/index_daily_fetcher.py` | `src/ingest/index_daily/index_daily_fetcher.py` |
| `src/pipeline/index_daily_mapper.py` | `src/ingest/index_daily/index_daily_mapper.py` |
| `src/pipeline/index_daily_persistence.py` | `src/ingest/index_daily/index_daily_persistence.py` |
| `src/pipeline/index_daily_preview.py` | `src/ingest/index_daily/index_daily_preview.py` |
| `src/pipeline/index_daily_service.py` | `src/ingest/index_daily/index_daily_service.py` |
| `src/pipeline/index_master.py` | `src/ingest/master/index_master.py` |
| `src/pipeline/index_scope.py` | `src/ingest/shared/index_scope.py` |
| `src/pipeline/ingest_check.py` | `src/quality/completeness/ingest_check.py` |
| `src/pipeline/init_symbols.py` | `src/ingest/master/init_symbols.py` |
| `src/pipeline/intraday_fetcher.py` | `src/ingest/stock_intraday/intraday_fetcher.py` |
| `src/pipeline/intraday_ingest.py` | `src/ingest/stock_intraday/intraday_ingest.py` |
| `src/pipeline/intraday_mapper.py` | `src/ingest/stock_intraday/intraday_mapper.py` |
| `src/pipeline/intraday_persistence.py` | `src/ingest/stock_intraday/intraday_persistence.py` |
| `src/pipeline/intraday_service.py` | `src/ingest/stock_intraday/intraday_service.py` |
| `src/pipeline/orderbook_snapshot.py` | `src/ingest/streaming/orderbook_snapshot.py` |
| `src/pipeline/pipeline_status.py` | `src/ingest/shared/pipeline_status.py` |
| `src/pipeline/refill.py` | `src/ingest/maintenance/refill.py` |
| `src/pipeline/stock_eod.py` | `src/ingest/workflows/stock_eod.py` |
| `src/pipeline/stock_intraday.py` | `src/ingest/workflows/stock_intraday.py` |
| `src/pipeline/streaming_snapshot.py` | `src/ingest/streaming/streaming_snapshot.py` |
| `src/pipeline/symbol_scope.py` | `src/ingest/shared/symbol_scope.py` |
| `src/pipeline/workflow_dates.py` | `src/ingest/workflows/workflow_dates.py` |
| `src/screener/README.md` | `src/research/screener/README.md` |
| `src/screener/README.vi.md` | `src/research/screener/README.vi.md` |
| `src/screener/__init__.py` | `src/research/screener/__init__.py` |
| `src/screener/config.py` | `src/research/screener/config.py` |
| `src/screener/configs/v2.json` | `src/research/screener/configs/v2.json` |
| `src/screener/methodologies/v2.md` | `src/research/screener/methodologies/v2.md` |
| `src/screener/methodologies/v2.vi.md` | `src/research/screener/methodologies/v2.vi.md` |
| `src/screener/rules.py` | `src/research/screener/rules.py` |
| `src/screener/rules_v2.py` | `src/research/screener/rules_v2.py` |
| `src/screener/service.py` | `src/research/screener/service.py` |
| `src/ssi/README.md` | RETIRED |
| `src/ssi/README.vi.md` | RETIRED |
| `src/ssi/__init__.py` | RETIRED |
| `src/ssi/api.py` | RETIRED |
| `src/ssi/streaming.py` | `src/ingest/streaming/payloads.py` |
| `src/ssi/v3.py` | `src/providers/ssi/clients/rest_v3.py` |
| `src/validation/README.md` | `src/quality/validators/README.md` |
| `src/validation/README.vi.md` | `src/quality/validators/README.vi.md` |
| `src/validation/__init__.py` | `src/quality/validators/__init__.py` |
| `src/validation/daily_validator.py` | `src/quality/validators/daily_validator.py` |
| `src/validation/index_daily_validator.py` | `src/quality/validators/index_daily_validator.py` |
| `src/validation/intraday_validator.py` | `src/quality/validators/intraday_validator.py` |
| `src/validation/logging_utils.py` | `src/quality/validators/logging_utils.py` |
| `src/validation/models.py` | `src/quality/validators/models.py` |
| `src/validation/phase0.py` | `src/quality/validators/phase0.py` |
| `src/validation/streaming_validator.py` | `src/quality/validators/streaming_validator.py` |
| `tests/analogs/test_core.py` | `tests/analogs/test_core.py` |
| `tests/analogs/test_eod_v2.py` | `tests/analogs/test_eod_v2.py` |
| `tests/analogs/test_pipeline_cli.py` | `tests/analogs/test_pipeline_cli.py` |
| `tests/analogs/test_runtime.py` | `tests/analogs/test_runtime.py` |
| `tests/cli/test_cli_refactor.py` | `tests/cli/test_cli_refactor.py` |
| `tests/cli/test_index_preview.py` | `tests/cli/test_index_preview.py` |
| `tests/data_contracts/test_engine.py` | `tests/data_contracts/test_engine.py` |
| `tests/data_contracts/test_mapper_compatibility.py` | `tests/data_contracts/test_mapper_compatibility.py` |
| `tests/data_preview/test_v3_client.py` | `tests/data_preview/test_v3_client.py` |
| `tests/data_sources/test_registry.py` | `tests/data_sources/test_registry.py` |
| `tests/data_sources/test_ssi_v3_stock_daily.py` | `tests/data_sources/test_ssi_v3_stock_daily.py` |
| `tests/features/test_daily_pagination.py` | `tests/features/test_daily_pagination.py` |
| `tests/features/test_feature_engine.py` | `tests/features/test_feature_engine.py` |
| `tests/features/test_feature_range_backfill.py` | `tests/features/test_feature_range_backfill.py` |
| `tests/features/test_feature_timeframe_policy.py` | `tests/features/test_feature_timeframe_policy.py` |
| `tests/features/test_intraday_pagination.py` | `tests/features/test_intraday_pagination.py` |
| `tests/features/test_issue99_contract.py` | `tests/features/test_issue99_contract.py` |
| `tests/features/test_long_history_parity.py` | `tests/features/test_long_history_parity.py` |
| `tests/foreign_features/test_foreign_calculator.py` | `tests/foreign_features/test_foreign_calculator.py` |
| `tests/foreign_features/test_foreign_service.py` | `tests/foreign_features/test_foreign_service.py` |
| `tests/index_features/test_calculator.py` | `tests/index_features/test_calculator.py` |
| `tests/index_features/test_pipeline.py` | `tests/index_features/test_pipeline.py` |
| `tests/ingest/test_daily_ingest_payload_reuse.py` | `tests/ingest/test_daily_ingest_payload_reuse.py` |
| `tests/ingest/test_daily_pipeline.py` | `tests/ingest/test_daily_pipeline.py` |
| `tests/ingest/test_fetch_one_day.py` | `tests/ingest/test_fetch_one_day.py` |
| `tests/ingest/test_index_daily_pipeline.py` | `tests/ingest/test_index_daily_pipeline.py` |
| `tests/ingest/test_ingest_check.py` | `tests/ingest/test_ingest_check.py` |
| `tests/ingest/test_intraday_ingest_pipeline.py` | `tests/ingest/test_intraday_ingest_pipeline.py` |
| `tests/ingest/test_master_data_pipeline.py` | `tests/ingest/test_master_data_pipeline.py` |
| `tests/ingest/test_ssi_api.py` | `tests/ingest/test_ssi_api.py` |
| `tests/ingest/test_stock_daily_room_rename_migration.py` | `tests/ingest/test_stock_daily_room_rename_migration.py` |
| `tests/ingest/test_stock_daily_v3_migration.py` | `tests/ingest/test_stock_daily_v3_migration.py` |
| `tests/ingest/test_symbol_scope.py` | `tests/ingest/test_symbol_scope.py` |
| `tests/inspectors/test_ssi_api_inspector.py` | `tests/inspectors/test_ssi_api_inspector.py` |
| `tests/inspectors/test_ssi_api_mapping.py` | `tests/inspectors/test_ssi_api_mapping.py` |
| `tests/inspectors/test_ssi_streaming_inspector.py` | `tests/inspectors/test_ssi_streaming_inspector.py` |
| `tests/pipeline/test_backfill_pipeline.py` | `tests/pipeline/test_backfill_pipeline.py` |
| `tests/pipeline/test_eod_dry_run.py` | `tests/pipeline/test_eod_dry_run.py` |
| `tests/pipeline/test_index_daily_date.py` | `tests/pipeline/test_index_daily_date.py` |
| `tests/pipeline/test_refill_pipeline.py` | `tests/pipeline/test_refill_pipeline.py` |
| `tests/pipeline/test_stock_eod_pipeline.py` | `tests/pipeline/test_stock_eod_pipeline.py` |
| `tests/pipeline/test_stock_eod_workflow.py` | `tests/pipeline/test_stock_eod_workflow.py` |
| `tests/pipeline/test_stock_intraday_pipeline.py` | `tests/pipeline/test_stock_intraday_pipeline.py` |
| `tests/pipeline/test_stock_intraday_workflow.py` | `tests/pipeline/test_stock_intraday_workflow.py` |
| `tests/pipeline/test_workflow_dates.py` | `tests/pipeline/test_workflow_dates.py` |
| `tests/screener/test_cli.py` | `tests/screener/test_cli.py` |
| `tests/screener/test_rules.py` | `tests/screener/test_rules.py` |
| `tests/screener/test_service.py` | `tests/screener/test_service.py` |
| `tests/screener/test_v2.py` | `tests/screener/test_v2.py` |
| `tests/streaming/test_streaming_ingest_pipeline.py` | `tests/streaming/test_streaming_ingest_pipeline.py` |
| `tests/validation/test_daily_validator.py` | `tests/validation/test_daily_validator.py` |
| `tests/validation/test_intraday_validator.py` | `tests/validation/test_intraday_validator.py` |
| `tests/validation/test_phase0.py` | `tests/validation/test_phase0.py` |
| `tests/validation/test_streaming_validator.py` | `tests/validation/test_streaming_validator.py` |

## 4. Files moved

- `scripts/backfill_stock_intraday_value.sql → scripts/maintenance/backfill_stock_intraday_value.sql`
- `scripts/check_complete_ssi_ingest.py → scripts/checks/check_complete_ssi_ingest.py`
- `scripts/check_ingest.py → scripts/checks/check_ingest.py`
- `scripts/check_ssi_ingest_schema.py → scripts/checks/check_ssi_ingest_schema.py`
- `scripts/check_supabase.py → scripts/checks/check_supabase.py`
- `scripts/eod_dry_run.py → scripts/previews/eod_dry_run.py`
- `scripts/fetch_one_day.py → scripts/maintenance/fetch_one_day.py`
- `scripts/phase0_reconcile_sample.py → scripts/checks/phase0_reconcile_sample.py`
- `scripts/phase0_validate_schema.py → scripts/checks/phase0_validate_schema.py`
- `scripts/run_features.py → scripts/previews/run_features.py`
- `scripts/snapshot_orderbook.py → scripts/capture/snapshot_orderbook.py`
- `scripts/snapshot_stream.py → scripts/capture/snapshot_stream.py`
- `scripts/ssi_api_inspector/README.md → scripts/inspectors/ssi_rest/README.md`
- `scripts/ssi_api_inspector/README.vi.md → scripts/inspectors/ssi_rest/README.vi.md`
- `scripts/ssi_api_inspector/__init__.py → scripts/inspectors/ssi_rest/__init__.py`
- `scripts/ssi_api_inspector/client.py → scripts/inspectors/ssi_rest/client.py`
- `scripts/ssi_api_inspector/datasets.py → scripts/inspectors/ssi_rest/datasets.py`
- `scripts/ssi_api_inspector/endpoints.py → scripts/inspectors/ssi_rest/endpoints.py`
- `scripts/ssi_api_inspector/inspect.py → scripts/inspectors/ssi_rest/inspect.py`
- `scripts/ssi_api_inspector/mapping.py → scripts/inspectors/ssi_rest/mapping.py`
- `scripts/ssi_streaming_inspector/README.md → scripts/inspectors/ssi_streaming/README.md`
- `scripts/ssi_streaming_inspector/README.vi.md → scripts/inspectors/ssi_streaming/README.vi.md`
- `scripts/ssi_streaming_inspector/__init__.py → scripts/inspectors/ssi_streaming/__init__.py`
- `scripts/ssi_streaming_inspector/inspect.py → scripts/inspectors/ssi_streaming/inspect.py`
- `scripts/ssi_streaming_inspector/output.py → scripts/inspectors/ssi_streaming/output.py`
- `scripts/ssi_streaming_inspector/registry.py → scripts/inspectors/ssi_streaming/registry.py`
- `src/analogs/README.md → src/research/analogs/README.md`
- `src/analogs/README.vi.md → src/research/analogs/README.vi.md`
- `src/analogs/__init__.py → src/research/analogs/__init__.py`
- `src/analogs/cli.py → src/research/analogs/cli.py`
- `src/analogs/core.py → src/research/analogs/core.py`
- `src/analogs/pipeline.py → src/research/analogs/pipeline.py`
- `src/analogs/profile.py → src/research/analogs/profile.py`
- `src/analogs/profiles/tplus_analog_core_eod_v1.json → src/research/analogs/profiles/tplus_analog_core_eod_v1.json`
- `src/analogs/profiles/tplus_analog_core_eod_v2.json → src/research/analogs/profiles/tplus_analog_core_eod_v2.json`
- `src/analogs/repository.py → src/research/analogs/repository.py`
- `src/analogs/runtime.py → src/research/analogs/runtime.py`
- `src/analogs/service.py → src/research/analogs/service.py`
- `src/analogs/validation.py → src/research/analogs/validation.py`
- `src/data_contracts/README.md → src/contracts/README.md`
- `src/data_contracts/README.vi.md → src/contracts/README.vi.md`
- `src/data_contracts/__init__.py → src/contracts/__init__.py`
- `src/data_contracts/definitions.json → src/contracts/definitions.json`
- `src/data_contracts/derived.py → src/contracts/derived.py`
- `src/data_contracts/engine.py → src/contracts/engine.py`
- `src/data_contracts/mappings/ssi_v3.json → src/contracts/mappings/ssi_v3.json`
- `src/data_contracts/registry.py → src/contracts/registry.py`
- `src/data_contracts/transforms.py → src/contracts/transforms.py`
- `src/data_sources/base.py → src/providers/ssi/base.py`
- `src/data_sources/registry.py → src/providers/ssi/registry.py`
- `src/data_sources/ssi_v3.py → src/providers/ssi/adapters/v3.py`
- `src/features/README.md → src/features/stock/README.md`
- `src/features/README.vi.md → src/features/stock/README.vi.md`
- `src/features/__init__.py → src/features/stock/__init__.py`
- `src/features/backfill.py → src/features/stock/backfill.py`
- `src/features/common.py → src/features/stock/common.py`
- `src/features/daily.py → src/features/stock/daily.py`
- `src/features/intraday.py → src/features/stock/intraday.py`
- `src/features/policy.py → src/features/stock/policy.py`
- `src/features/runner.py → src/features/stock/runner.py`
- `src/features/runtime.py → src/features/stock/runtime.py`
- `src/foreign_features/README.md → src/features/foreign/README.md`
- `src/foreign_features/README.vi.md → src/features/foreign/README.vi.md`
- `src/foreign_features/__init__.py → src/features/foreign/__init__.py`
- `src/foreign_features/calculator.py → src/features/foreign/calculator.py`
- `src/foreign_features/calendar.py → src/features/foreign/calendar.py`
- `src/foreign_features/loader.py → src/features/foreign/loader.py`
- `src/foreign_features/persistence.py → src/features/foreign/persistence.py`
- `src/foreign_features/service.py → src/features/foreign/service.py`
- `src/foreign_features/validator.py → src/features/foreign/validator.py`
- `src/index_features/README.md → src/features/index/README.md`
- `src/index_features/README.vi.md → src/features/index/README.vi.md`
- `src/index_features/__init__.py → src/features/index/__init__.py`
- `src/index_features/calculator.py → src/features/index/calculator.py`
- `src/index_features/completeness.py → src/features/index/completeness.py`
- `src/index_features/pipeline.py → src/features/index/pipeline.py`
- `src/index_features/repository.py → src/features/index/repository.py`
- `src/pipeline/README.md → src/ingest/README.md`
- `src/pipeline/README.vi.md → src/ingest/README.vi.md`
- `src/pipeline/__init__.py → src/ingest/__init__.py`
- `src/pipeline/backfill.py → src/ingest/maintenance/backfill.py`
- `src/pipeline/daily.py → src/ingest/stock_daily/daily.py`
- `src/pipeline/daily_fetcher.py → src/ingest/stock_daily/daily_fetcher.py`
- `src/pipeline/daily_mapper.py → src/ingest/stock_daily/daily_mapper.py`
- `src/pipeline/daily_persistence.py → src/ingest/stock_daily/daily_persistence.py`
- `src/pipeline/daily_service.py → src/ingest/stock_daily/daily_service.py`
- `src/pipeline/date_utils.py → src/ingest/shared/date_utils.py`
- `src/pipeline/eod_dry_run.py → src/diagnostics/eod_dry_run.py`
- `src/pipeline/fetch_one_day.py → src/diagnostics/fetch_one_day.py`
- `src/pipeline/index_backfill.py → src/ingest/index_daily/index_backfill.py`
- `src/pipeline/index_completeness.py → src/quality/completeness/index_completeness.py`
- `src/pipeline/index_daily.py → src/ingest/index_daily/index_daily.py`
- `src/pipeline/index_daily_fetcher.py → src/ingest/index_daily/index_daily_fetcher.py`
- `src/pipeline/index_daily_mapper.py → src/ingest/index_daily/index_daily_mapper.py`
- `src/pipeline/index_daily_persistence.py → src/ingest/index_daily/index_daily_persistence.py`
- `src/pipeline/index_daily_preview.py → src/ingest/index_daily/index_daily_preview.py`
- `src/pipeline/index_daily_service.py → src/ingest/index_daily/index_daily_service.py`
- `src/pipeline/index_master.py → src/ingest/master/index_master.py`
- `src/pipeline/index_scope.py → src/ingest/shared/index_scope.py`
- `src/pipeline/ingest_check.py → src/quality/completeness/ingest_check.py`
- `src/pipeline/init_symbols.py → src/ingest/master/init_symbols.py`
- `src/pipeline/intraday_fetcher.py → src/ingest/stock_intraday/intraday_fetcher.py`
- `src/pipeline/intraday_ingest.py → src/ingest/stock_intraday/intraday_ingest.py`
- `src/pipeline/intraday_mapper.py → src/ingest/stock_intraday/intraday_mapper.py`
- `src/pipeline/intraday_persistence.py → src/ingest/stock_intraday/intraday_persistence.py`
- `src/pipeline/intraday_service.py → src/ingest/stock_intraday/intraday_service.py`
- `src/pipeline/orderbook_snapshot.py → src/ingest/streaming/orderbook_snapshot.py`
- `src/pipeline/pipeline_status.py → src/ingest/shared/pipeline_status.py`
- `src/pipeline/refill.py → src/ingest/maintenance/refill.py`
- `src/pipeline/stock_eod.py → src/ingest/workflows/stock_eod.py`
- `src/pipeline/stock_intraday.py → src/ingest/workflows/stock_intraday.py`
- `src/pipeline/streaming_snapshot.py → src/ingest/streaming/streaming_snapshot.py`
- `src/pipeline/symbol_scope.py → src/ingest/shared/symbol_scope.py`
- `src/pipeline/workflow_dates.py → src/ingest/workflows/workflow_dates.py`
- `src/screener/README.md → src/research/screener/README.md`
- `src/screener/README.vi.md → src/research/screener/README.vi.md`
- `src/screener/__init__.py → src/research/screener/__init__.py`
- `src/screener/config.py → src/research/screener/config.py`
- `src/screener/configs/v2.json → src/research/screener/configs/v2.json`
- `src/screener/methodologies/v2.md → src/research/screener/methodologies/v2.md`
- `src/screener/methodologies/v2.vi.md → src/research/screener/methodologies/v2.vi.md`
- `src/screener/rules.py → src/research/screener/rules.py`
- `src/screener/rules_v2.py → src/research/screener/rules_v2.py`
- `src/screener/service.py → src/research/screener/service.py`
- `src/ssi/v3.py → src/providers/ssi/clients/rest_v3.py`
- `src/validation/README.md → src/quality/validators/README.md`
- `src/validation/README.vi.md → src/quality/validators/README.vi.md`
- `src/validation/__init__.py → src/quality/validators/__init__.py`
- `src/validation/daily_validator.py → src/quality/validators/daily_validator.py`
- `src/validation/index_daily_validator.py → src/quality/validators/index_daily_validator.py`
- `src/validation/intraday_validator.py → src/quality/validators/intraday_validator.py`
- `src/validation/logging_utils.py → src/quality/validators/logging_utils.py`
- `src/validation/models.py → src/quality/validators/models.py`
- `src/validation/phase0.py → src/quality/validators/phase0.py`
- `src/validation/streaming_validator.py → src/quality/validators/streaming_validator.py`

## 5. Files modified (existing tracked paths)

- `.env.example`
- `.github/workflows/README.md`
- `.github/workflows/README.vi.md`
- `.github/workflows/index-eod-v2.yml`
- `.github/workflows/stock-eod.yml`
- `.github/workflows/stock-intraday.yml`
- `README.md`
- `README.vi.md`
- `docs/ARCHITECTURE_DECISIONS.md`
- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/CURRENT_STATE.md`
- `docs/DATA_PIPELINE.md`
- `docs/PROJECT_OVERVIEW.md`
- `docs/README.md`
- `docs/README.vi.md`
- `docs/STOCK_EOD_PIPELINE.md`
- `docs/STOCK_EOD_PIPELINE.vi.md`
- `docs/STOCK_INTRADAY_PIPELINE.md`
- `docs/STOCK_INTRADAY_PIPELINE.vi.md`
- `docs/phase0/PHASE0_VALIDATION_REPORT.md`
- `docs/phase0/PHASE0_VALIDATION_REPORT.vi.md`
- `docs/phase1/README.md`
- `docs/phase1/README.vi.md`
- `main.py`
- `requirements.txt`
- `scripts/README.md`
- `scripts/README.vi.md`
- `src/README.md`
- `src/README.vi.md`
- `src/config.py`
- `src/database/README.md`
- `src/database/README.vi.md`
- `src/features/README.md`
- `src/features/README.vi.md`
- `src/features/__init__.py`
- `tests/analogs/test_core.py`
- `tests/analogs/test_eod_v2.py`
- `tests/analogs/test_pipeline_cli.py`
- `tests/analogs/test_runtime.py`
- `tests/cli/test_cli_refactor.py`
- `tests/cli/test_index_preview.py`
- `tests/data_contracts/test_engine.py`
- `tests/data_contracts/test_mapper_compatibility.py`
- `tests/data_preview/test_v3_client.py`
- `tests/data_sources/test_registry.py`
- `tests/data_sources/test_ssi_v3_stock_daily.py`
- `tests/features/test_daily_pagination.py`
- `tests/features/test_feature_engine.py`
- `tests/features/test_feature_range_backfill.py`
- `tests/features/test_feature_timeframe_policy.py`
- `tests/features/test_intraday_pagination.py`
- `tests/features/test_issue99_contract.py`
- `tests/features/test_long_history_parity.py`
- `tests/foreign_features/test_foreign_calculator.py`
- `tests/foreign_features/test_foreign_service.py`
- `tests/index_features/test_calculator.py`
- `tests/index_features/test_pipeline.py`
- `tests/ingest/test_daily_ingest_payload_reuse.py`
- `tests/ingest/test_daily_pipeline.py`
- `tests/ingest/test_fetch_one_day.py`
- `tests/ingest/test_index_daily_pipeline.py`
- `tests/ingest/test_ingest_check.py`
- `tests/ingest/test_intraday_ingest_pipeline.py`
- `tests/ingest/test_master_data_pipeline.py`
- `tests/ingest/test_ssi_api.py`
- `tests/ingest/test_stock_daily_room_rename_migration.py`
- `tests/ingest/test_stock_daily_v3_migration.py`
- `tests/ingest/test_symbol_scope.py`
- `tests/inspectors/test_ssi_api_inspector.py`
- `tests/inspectors/test_ssi_api_mapping.py`
- `tests/inspectors/test_ssi_streaming_inspector.py`
- `tests/pipeline/test_backfill_pipeline.py`
- `tests/pipeline/test_eod_dry_run.py`
- `tests/pipeline/test_index_daily_date.py`
- `tests/pipeline/test_refill_pipeline.py`
- `tests/pipeline/test_stock_eod_pipeline.py`
- `tests/pipeline/test_stock_eod_workflow.py`
- `tests/pipeline/test_stock_intraday_pipeline.py`
- `tests/pipeline/test_stock_intraday_workflow.py`
- `tests/pipeline/test_workflow_dates.py`
- `tests/screener/test_cli.py`
- `tests/screener/test_rules.py`
- `tests/screener/test_service.py`
- `tests/screener/test_v2.py`
- `tests/streaming/test_streaming_ingest_pipeline.py`
- `tests/validation/test_daily_validator.py`
- `tests/validation/test_intraday_validator.py`
- `tests/validation/test_phase0.py`
- `tests/validation/test_streaming_validator.py`

## 6. Files created (excluding move destinations)

- `docs/RESTRUCTURE_AUDIT.md`
- `docs/RESTRUCTURE_MAPPING.json`
- `docs/RESTRUCTURE_REPORT.md`
- `docs/RETIRED_TEST_INVENTORY.json`
- `scripts/capture/README.md`
- `scripts/capture/README.vi.md`
- `scripts/capture/__init__.py`
- `scripts/checks/README.md`
- `scripts/checks/README.vi.md`
- `scripts/checks/__init__.py`
- `scripts/inspectors/README.md`
- `scripts/inspectors/README.vi.md`
- `scripts/inspectors/__init__.py`
- `scripts/maintenance/README.md`
- `scripts/maintenance/README.vi.md`
- `scripts/maintenance/__init__.py`
- `scripts/previews/README.md`
- `scripts/previews/README.vi.md`
- `scripts/previews/__init__.py`
- `src/cli/README.md`
- `src/cli/README.vi.md`
- `src/cli/__init__.py`
- `src/cli/analogs.py`
- `src/cli/common.py`
- `src/cli/features.py`
- `src/cli/foreign.py`
- `src/cli/index.py`
- `src/cli/maintenance.py`
- `src/cli/parser.py`
- `src/cli/screener.py`
- `src/cli/stock.py`
- `src/cli/streaming.py`
- `src/diagnostics/README.md`
- `src/diagnostics/README.vi.md`
- `src/diagnostics/__init__.py`
- `src/ingest/index_daily/README.md`
- `src/ingest/index_daily/README.vi.md`
- `src/ingest/index_daily/__init__.py`
- `src/ingest/maintenance/README.md`
- `src/ingest/maintenance/README.vi.md`
- `src/ingest/maintenance/__init__.py`
- `src/ingest/master/README.md`
- `src/ingest/master/README.vi.md`
- `src/ingest/master/__init__.py`
- `src/ingest/shared/README.md`
- `src/ingest/shared/README.vi.md`
- `src/ingest/shared/__init__.py`
- `src/ingest/stock_daily/README.md`
- `src/ingest/stock_daily/README.vi.md`
- `src/ingest/stock_daily/__init__.py`
- `src/ingest/stock_intraday/README.md`
- `src/ingest/stock_intraday/README.vi.md`
- `src/ingest/stock_intraday/__init__.py`
- `src/ingest/streaming/README.md`
- `src/ingest/streaming/README.vi.md`
- `src/ingest/streaming/__init__.py`
- `src/ingest/streaming/payloads.py`
- `src/ingest/workflows/README.md`
- `src/ingest/workflows/README.vi.md`
- `src/ingest/workflows/__init__.py`
- `src/providers/README.md`
- `src/providers/README.vi.md`
- `src/providers/__init__.py`
- `src/providers/ssi/README.md`
- `src/providers/ssi/README.vi.md`
- `src/providers/ssi/__init__.py`
- `src/providers/ssi/adapters/README.md`
- `src/providers/ssi/adapters/README.vi.md`
- `src/providers/ssi/adapters/__init__.py`
- `src/providers/ssi/capabilities.py`
- `src/providers/ssi/clients/README.md`
- `src/providers/ssi/clients/README.vi.md`
- `src/providers/ssi/clients/__init__.py`
- `src/quality/README.md`
- `src/quality/README.vi.md`
- `src/quality/__init__.py`
- `src/quality/completeness/README.md`
- `src/quality/completeness/README.vi.md`
- `src/quality/completeness/__init__.py`
- `src/research/README.md`
- `src/research/README.vi.md`
- `src/research/__init__.py`
- `tests/cli/test_capability_retirement.py`
- `tests/ingest/test_provider_boundary.py`

## 7. Files deleted (excluding moves)

- `src/data_contracts/mappings/ssi_v2.json`
- `src/data_sources/__init__.py`
- `src/data_sources/ssi_v2.py`
- `src/engine/README.md`
- `src/engine/README.vi.md`
- `src/engine/__init__.py`
- `src/engine/data_quality.py`
- `src/ssi/README.md`
- `src/ssi/README.vi.md`
- `src/ssi/__init__.py`
- `src/ssi/api.py`
- `src/ssi/streaming.py`

## 8. SSI v2 removal inventory

- Deleted `src/ssi/api.py`, `src/data_sources/ssi_v2.py`, old source package initializers and `src/contracts/mappings/ssi_v2.json` (formerly data_contracts).
- Deleted classic SignalR connection/authentication in `src/ssi/streaming.py`; retained only pure offline historical payload decoding under ingest/streaming. The streaming inspector has a no-service unavailable wrapper.
- Replaced v2 daily/index fetching, mapping/service fallback branches and index preview. Removed unconsumed legacy daily aliases. Disabled intraday/master/streaming services and combined one-day fetch, combined dry-run, backfill/refill before services or stages run.
- Registry has v3 entries only; explicit v2 source raises unsupported-source before client/DB construction, including EOD and empty/weekend backfills.
- Removed v2 inspector endpoint registrations, request builders, authentication, consumer credentials, runtime URLs and streaming settings. Removed the websocket client dependency.
- Retired unused `src/engine/data_quality.py` with obsolete count/recompute behavior; no active consumers existed.
- Source/script/workflow runtime scans find no v2 IDs, classes, URLs, consumer credentials or old hub registration. Historical offline frame utility comments may mention SignalR without implementing a connection.
- Immutable historical SQL provenance references remain intact. Test retirement details are in `RETIRED_TEST_INVENTORY.json`; valuable active/canonical/feature/research coverage was retained or migrated to verified v3 fixtures.

## 9. Active SSI v3 capabilities

Stock Daily uses the existing verified securitiesSummary client/adapter, pagination, raw payload/hash/source, derived canonical mapping, validation, clean persistence, completeness and daily backfill. Index Daily uses the existing verified indexSummary mapping, active persisted master selection, raw/clean writes, backfill and check. Index preview uses that adapter and never constructs a DB client. Empty master scope fails rather than generating records. Ingestion remains separate from all downstream features/research.

## 10. Disabled capabilities and future locations

- Intraday ingestion: `src/ingest/stock_intraday/`, future verified mapping/fetch adapter in `src/providers/ssi/adapters/`.
- Master synchronization: `src/ingest/master/`, future dedicated verified provider adapter/mapping; operator status and historical rows preserved.
- Streaming/orderbook capture: `src/ingest/streaming/`; requires independently verified current protocol/authentication. Offline historical decoders do not establish compatibility.
- Combined `backfill`, `refill`, one-day fetch and live combined diagnostics fail before any active daily branch starts.

Unavailable production commands parse existing arguments, emit FAILED/NOT_IMPLEMENTED, exit 1 and make no API/database calls. No fake v3 adapter or fallback is supplied. Future v4 requires client/adapter/mapping/registry entries, not a repository-wide restructure; v4 is not implemented.

## 11. CLI compatibility results

All 32 commands display help. Active command argument/JSON/status contracts and aliases remain covered by regression tests. Stock daily/index/feature/foreign/screener/analog routes work with offline/injected boundaries. Historical clean 1m feature computation remains active; persisted stock feature timeframes remain 1d/15m/60m. Explicit SSI v2 returns exit 2 before services. Disabled commands return exit 1 with machine-readable failure; missing parser-required arguments still return exit 2 normally.

## 12. GitHub Actions

Stock EOD retains 09:30 UTC Mon–Fri and index EOD retains 01:30 UTC Tue–Sat, including existing date resolution and scope semantics. Resolver module paths were updated. V2 credentials/source choices were removed. The index workflow filename remains index-eod-v2.yml (workflow naming, not a v2 REST provider); only one index schedule exists. Tests and explicit feature workflow behavior/schedules remain unchanged. Intraday has no scheduled trigger or credentials: a manual no-service diagnostic emits NOT_IMPLEMENTED and exits 1. No automatic master or streaming path remains.

## 13–16. Database, production data, migration and backfill

Schema/RPC/table/column/conflict-key/index contracts: unchanged. Root schema and 44 protected SQL files matched HEAD byte-for-byte. Migration history is immutable. No production records, source provenance, raw payloads, master statuses, clean rows or features were read/written by integration smoke tests; none were relabeled/deleted. No migration or backfill is required. Future capability implementation/backfills are separate tasks. Existing clean historical data continues to support feature/research calculations under unchanged input-quality rules.

## 17. Exact test and verification commands

```bash
# Baseline (before restructuring)
.venv/bin/pytest -q > /tmp/trading-baseline.log 2>&1
.venv/bin/python -m compileall -q main.py src scripts tests
.venv/bin/python main.py --help > work/baseline-help.txt

# Targeted active domains
.venv/bin/pytest -q tests/data_sources tests/data_contracts tests/features tests/foreign_features tests/analogs tests/screener > work/targeted.log 2>&1
.venv/bin/pytest -q tests/cli tests/ingest tests/pipeline tests/streaming tests/validation > work/targeted3.log 2>&1
.venv/bin/pytest -q tests/ingest/test_provider_boundary.py tests/ingest/test_index_daily_pipeline.py tests/cli/test_index_preview.py tests/cli/test_capability_retirement.py

# Final verification
.venv/bin/python -m pytest -q -rs > work/full-release.log 2>&1
.venv/bin/python -m compileall -q main.py src scripts tests
.venv/bin/python main.py --help > work/final-help.txt
.venv/bin/python scripts/inspectors/ssi_rest/inspect.py list > work/inspector-list.txt
PYTHONPATH=. .venv/bin/python work/verify_structure.py
git diff --check

# Smoke results: exit 1 / FAILED-NOT_IMPLEMENTED and exit 2 / unsupported source
.venv/bin/python main.py stock-intraday 19/10/2026 --symbols SSI
.venv/bin/python main.py stock-eod 19/10/2026 --symbols SSI --data-source ssi_v2
```

Baseline: 661 passed, 7 skipped. An initial post-move run failed on stale imports and retired behavior expectations; those were corrected before final verification. Intermediate targeted3 had one invalid new streaming test fixture (missing required --channels); this was corrected. Final focused provider/preview/retirement checks: 50 passed. Final full suite: **577 passed, 7 skipped, 0 failed** (15.87 seconds). Reduced count reflects retired v2 transport/mapping and legacy-success parameter cases, replaced with no-I/O retirement tests and v3 fixtures; inventory provided.

## 18. PASS / FAIL / SKIPPED results

| Check | Result |
| --- | --- |
| Full Python suite | PASS: 577 passed; 7 PostgreSQL tests skipped |
| Compileall main/src/scripts/tests | PASS |
| CLI help | PASS: all 32 commands |
| Module imports | PASS: 149 modules |
| Static module-top-level import cycles | PASS: zero |
| Provider → ingest/database dependency scan | PASS: none |
| Analytical AST parity excluding imports | PASS: 34 modules |
| JSON asset byte parity | PASS: 5 moved assets |
| Schema/SQL byte parity | PASS: 44 protected SQL files |
| Bilingual package README coverage | PASS |
| No retired runtime source/auth/client references | PASS |
| Workflow paths / schedules / disabled intraday assertions | PASS |
| git diff --check | PASS |
| PostgreSQL RPC integration | SKIPPED: TEST_DATABASE_URL unavailable; no local PostgreSQL binaries and Docker socket access denied |
| Live SSI/Supabase smoke | NOT_RUN: no configured credentials; production writes prohibited |
| Latest remote dev verification | PASS: GitHub connector GET /repos/quangnguyenhuynh/tradingTplus/branches/dev returned 90a57b1b0a2eca80f04fbbe01f36b5d9856d3db5 |

A read-only GitHub connector request to `https://api.github.com/repos/quangnguyenhuynh/tradingTplus/branches/dev` verified remote dev SHA `90a57b1b0a2eca80f04fbbe01f36b5d9856d3db5`. Shell `git fetch origin dev` was unsuccessful because the proxy was unreachable; the connector provided independent verification.

## 19. Remaining risks

- Local checkout is `90a57b1b0a2eca80f04fbbe01f36b5d9856d3db5` on `work`. Locally recorded origin/dev is `f6e35a52c5a0bd6ce5461893b5d3cc95091198ff`, an ancestor. The connected GitHub branch API verified remote dev equals HEAD at 90a57b1b0a2eca80f04fbbe01f36b5d9856d3db5; the local origin/dev tracking ref remains stale because shell git fetch failed.
- Offline/injected tests establish application contracts, not current remote provider availability, production schema deployment or live completeness.
- PostgreSQL atomic-replacement tests need the existing CI PostgreSQL service; they were already skipped in the baseline.
- External code importing moved internal modules must update paths. Supported CLI names and stock feature top-level exports remain. Retired v2 APIs are intentionally unavailable.
- Raw-to-clean reconciliation cannot remap retired/unknown historical sources through v3; it reports UNKNOWN while retaining safe clean-to-feature checks. Historical source data remains untouched.
- Intraday/master/streaming ingestion remains intentionally unavailable until verified adapters are implemented. This is approved behavior, not an unfinished v3 imitation.

## 20. Recommended next step and rollback

Run the existing CI suite on the verified dev base with its PostgreSQL service. Then perform separately scoped, read-only SSI v3 daily/index smoke checks with configured credentials. Do not re-enable retired ingestion schedules or run production backfills as part of review. Rollback is code-only: revert this restructuring patch/deployment; no database rollback is needed.
