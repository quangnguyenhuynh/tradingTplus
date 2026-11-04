# SSI v3 indexSummary → `index_daily` mapping

[Tiếng Việt](SSI_DAILY_INDEX_MAPPING.vi.md)

`public.index_daily` contract **3.0.0** is produced from SSI v3 `GET /api/v3/data/indexSummary`. SSI v2 `DailyIndex` is retired; legacy RAW remains immutable and is flagged as unverified provenance, not remapped with v3.

The request `index` supplies `index_code`; a supplied index/indexCode/indexId must agree after uppercase normalization. No missing response field is invented. Raw response items are stored unchanged with source `SSI_v3_indexSummary` before clean mapping and validation. Unknown future fields therefore remain available for remapping.

| SSI v3 item field | Clean column |
|---|---|
| request/context `index` | `index_code` |
| `tradingDate` | `trading_date` |
| `indexValue` | `index_value` |
| `indexChange` | `index_change` |
| `indexChangePercentage` | `index_change_percentage` |
| `totalTrade` / `totalTradeValue` | `total_trade_volume` / `total_trade_value` |
| `totalMatch` / `totalMatchValue` | `total_match_volume` / `total_match_value` |
| `totalDeal` / `totalDealValue` | `total_deal_volume` / `total_deal_value` |
| `totalAdvanceStock` / `totalCeilingStock` | `total_advance_stock` / `total_ceiling_stock` |
| `totalDeclineStock` / `totalFloorStock` | `total_decline_stock` / `total_floor_stock` |
| `totalNoChangeStock` | `total_no_change_stock` |
| `totalPropBuy` / `totalPropBuyValue` | `total_prop_buy_volume` / `total_prop_buy_value` |
| `totalPropSell` / `totalPropSellValue` | `total_prop_sell_volume` / `total_prop_sell_value` |
| `totalBuyForeign` / `totalBuyForeignValue` | `total_foreign_buy_volume` / `total_foreign_buy_value` |
| `totalSellForeign` / `totalSellForeignValue` | `total_foreign_sell_volume` / `total_foreign_sell_value` |
| `netPurchasesForeignVolume` / `netPurchasesForeignValue` | `net_foreign_purchase_volume` / `net_foreign_purchase_value` |

Monetary, level and percentage fields use exact Decimal; volumes/counts use exact integers. Signed net monetary values retain their signs and fractions. Mapping normalizes only representation and type. For example, `indexChange: "10.02"` becomes `index_change: 10.02`, never `0.1002`. `indexChangePercentage` remains in SSI's provider percent unit and is not divided by 100. Missing optional values remain `NULL`.

The current numeric migration `20261104_daily_numeric_precision.sql` changes functions only and never empties/rewrites history. Earlier rebuild instructions are historical and must not be reused as numeric deployment instructions. Owner applies the new migration manually and reruns Index only if an exact audit demonstrates a need. No automatic feature backfill. [Field classification, exact transport, read-only diagnostics and owner deployment](DAILY_NUMERIC_PRECISION.md).
