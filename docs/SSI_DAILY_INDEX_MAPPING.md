# SSI v3 indexSummary → `index_daily` mapping

`public.index_daily` contract **2.0.0** is produced from SSI v3 `GET /api/v3/data/indexSummary`. SSI v2 `DailyIndex` is deprecated for production clean data because its change fields are not reliable; its client/mapping remains available for read-only inspection and its existing `index_raw_daily` evidence is retained.

The request `index` supplies `index_code`; no response identity field is invented. Raw response items are stored unchanged with source `SSI_v3_indexSummary` before clean mapping and validation. Unknown future fields therefore remain available for remapping.

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

Mapping normalizes only representation and type. For example, `indexChange: "10.02"` becomes `index_change: 10.02`, never `0.1002`. `indexChangePercentage` remains in SSI's provider percent unit and is not divided by 100. Missing optional values remain `NULL`.

The migration empties the untrusted v2 clean history without modifying `index_raw_daily`. After applying it manually, run an SSI v3 clean backfill, validate it, and then run the independent index-feature backfill. Ingest never calculates features.
