# src/contracts

Provider-neutral canonical contracts, transform engine and explicit source dictionaries.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

Modules:

- `derived.py`
- `engine.py`
- `registry.py`
- `transforms.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.

## SSI v3 intraday — source fields and nullable value

Owner-provided live SSI excerpts for 2026-10-20 verify `ohlc.tradingDate` in `YYYY/MM/DD HH:mm:ss`, source `ohlc.value`, and terminal `{"code":204,"msg":"No Content"}`. This exact source-local timestamp is explicitly interpreted in `Asia/Ho_Chi_Minh` and normalized to UTC; valid explicit-offset forms remain supported. The legacy `time` alias still requires an explicit timezone. Date-only/time-only and arbitrary naive formats remain rejected; no request-date fabrication or minute shifting.

Canonical v3 `value` is **SSI-reported intraday candle value**, parsed exactly as a nonnegative signed-BIGINT integer without float conversion. There is **no calculated estimate or fallback**. Absent/null/empty source value stays NULL with SOURCE_VALUE_MISSING; malformed/non-finite/fractional/negative/overflow value rejects the candidate. Zero stays zero. Source-value presence, numeric validity and preservation are reported separately from independently verified market-data semantics (still false).

The verified 204/No Content envelope terminates OHLC 1m paging only without conflicting payload/error markers and after metadata/count checks. Its original envelope is retained and termination is provider_no_content_204. Short nonempty pages never terminate by themselves; repeats, wrong totals, malformed/errors and page-limit truncation still fail. --limit controls display only; --full-json retains received raw pages, candidates and diagnostics.

The supplied day had 226 unique rows over 23 nonempty pages then page 24, descending order, 135 morning/90 afternoon/one 14:45 candle. These are owner-reported observations for that day, not a universal count or a formula rule. Only two real candle objects and the terminal envelope were supplied; offline replay verifies those 2/2 without reconstructing missing rows. Agent live rerun: NOT_RUN (no credentials). Bar-start/end, independent value/turnover semantics and market completeness remain unverified. Production ingestion/scheduling remains disabled; preview performs zero database reads/writes.

[Mapping rules and persistence guard](../../docs/STOCK_INTRADAY_PIPELINE.md)

## Security catalog mapping — 27 October 2026

SSI v3 symbol_list mapping 1.1.0-preview maps symbolNameVi→stock_name, board→market/exchange, stockType→security_type. Optional missing values stay NULL; unknown type stays source text. Daily/intraday/index contracts are unchanged. Inspector PASS validates row mapping only, not complete board/universe or persistence. [Evidence and sample provenance](../../docs/SSI_V3_MASTER_EVIDENCE.md).
