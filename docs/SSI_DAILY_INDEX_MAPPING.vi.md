# Mapping SSI v3 indexSummary → index_daily

[English](SSI_DAILY_INDEX_MAPPING.md)

Contract/mapping **3.0.0** dùng GET /api/v3/data/indexSummary; không đổi endpoint hoặc đơn vị. V2 đã retired, giữ RAW legacy bất biến và đánh dấu provenance chưa xác minh, không remap bằng v3.

Request index cung cấp index_code. Nếu payload có index/indexCode/indexId phải khớp sau uppercase; không dựng field response bị thiếu. RAW source SSI_v3_indexSummary được lưu nguyên semantic trước CLEAN.

| Field SSI v3 | Cột CLEAN |
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

Tiền/level/phần trăm dùng Decimal, volume/count dùng integer chính xác; net money được âm và có phần lẻ. indexChange 10.02 giữ 10.02, không đổi thành 0.1002. Percentage không chia 100. Optional thiếu giữ NULL; level hữu hạn dương là bắt buộc. Numeric sai reject toàn row; component/net mismatch cảnh báo, không sửa số nguồn. Không thêm quarantine/log/status framework Index trong task này.

Migration mới 20261104_daily_numeric_precision.sql chỉ đổi/thêm function, không empty/rewrite lịch sử. Hướng dẫn rebuild cũ là lịch sử, không chạy lại để deploy numeric. Owner apply thủ công; chỉ rerun Index khi exact audit có bằng chứng cần thiết. Không tự backfill features.

[Matrix field, transport chính xác, diagnostic chỉ đọc, SQL/deploy/rollback](DAILY_NUMERIC_PRECISION.vi.md).
