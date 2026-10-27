# SSI v3 securitiesByBoard evidence — 26–27 October 2026

[Tiếng Việt](SSI_V3_MASTER_EVIDENCE.vi.md)

The owner supplied the following verified read-only observations in the task,
not credentials or complete verbatim response files:

| Request | HTTP | JSON shape | Observed records |
| --- | --- | --- | --- |
| GET /api/v3/data/securitiesByBoard?board=HOSE | 200 | array | 793 |
| GET /api/v3/data/securitiesByBoard?board=HNX | 200 | array | 410 |
| GET /api/v3/data/securitiesByBoard?board=UPCOM | 200 | array | 851 |

Total observed: 2,054. Counts are historical anomaly references, not expected
permanent totals, pagination metadata or proof of authoritative market coverage.
The endpoint exposes no provider total or pagination metadata. Only these board
requests are used; no synthetic pageIndex/pageSize or source fallback.

Verified field names: symbol, symbolNameVi, symbolNameEn, board, stockType,
lotSize, listedShare, firstTradingDate, lastTradingDate, maturityDate,
cwUnderlyingSymbol, cwExercisePrice, cwExecutionRatio, icbCode, icbName, iIndex,
iNav, openInterest, settlementPrice. Known stockType examples: Stock, Bond,
ETF Product, Investment Fund; unknown and NULL values are allowed. HNX may omit
listedShare, symbolNameEn and other descriptions. UPCoM date example:
2026/01/27. Empty optional dates mean unknown/NULL.

The owner evidence establishes the mapped field contract and the three array
requests. It does not establish arbitrary detail-field semantics, authoritative
market totals, index definitions, index membership or future SSI v4/v5 support.
No issuer, issue_date or tick fields are invented.

Fixture provenance: tests/fixtures/data_preview/ssi_v3_master_contract_samples.json
contains representative illustrative values using these verified field names,
types and date formats. Its rows are NOT verbatim live SSI payloads, and the full
2,054 records were not reconstructed. Mock HTTP tests verify implementation,
not a new live-source observation. Neither these samples nor an inspector mapping
PASS prove market completeness.

Agent verification: no live SSI request (credentials absent). Read-only catalog
queries on TradingTPus_DS confirmed both primary keys and no securities→symbols
foreign key. No Supabase write, migration or price-data backfill.

[Guarded sync policy and owner procedure](../src/ingest/master/README.md).
