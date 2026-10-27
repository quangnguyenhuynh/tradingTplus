# src — bản đồ kiến trúc và vận hành

[English](README.md)

`main.py → src/cli → src/ingest` điều phối ingest. `src/providers/ssi` chọn client/adapter v3; `src/contracts` map/validate contract, `src/quality` kiểm tra chất lượng. `src/database` giữ persistence raw/clean riêng. `src/features/{stock,foreign,index}` đọc clean độc lập; `src/research/{screener,analogs}` là tầng nghiên cứu sau feature. Ingest không tự tính feature hay chạy nghiên cứu.

| Domain | Vai trò |
| --- | --- |
| [cli](cli/README.vi.md) | Parse / preflight / dispatch |
| [providers/ssi](providers/ssi/README.vi.md) | SSI v3 clients, adapters, readiness registry |
| [contracts](contracts/README.vi.md) | Canonical mappings and validation |
| [ingest](ingest/README.vi.md) | Stock/index source orchestration, raw/clean persistence |
| [quality](quality/README.vi.md) | Validators and completeness |
| [features/stock](features/stock/README.vi.md) | stock_daily → 1d; clean 1m → 15m/60m |
| [features/foreign](features/foreign/README.vi.md) | stock_daily → stock_foreign_features_daily |
| [features/index](features/index/README.vi.md) | index_daily → index_features_daily |
| [research/screener](research/screener/README.vi.md) | V1/V2 preview and explicit apply |
| [research/analogs](research/analogs/README.vi.md) | Same-symbol EOD snapshots/outcomes/research |

Đối chiếu commit `b5cb3276` trên `dev` (PR #178). Chạy tại thư mục gốc repository. Ngày và mã trong ví dụ chỉ minh họa; kiểm tra nguồn và chọn đúng phạm vi trước khi chạy. Chỉ kiểm tra cú pháp offline, chưa gọi SSI hay Supabase thật.

Ingest Stock Daily (`securitiesSummary`) và Index Daily (`indexSummary`) qua SSI v3: ACTIVE. Feature stock, foreign và index: ACTIVE trên dữ liệu clean đã lưu. Screener và Historical Analog: RESEARCH_ACTIVE. Master sync có orchestrator guard, symbols/securities READY có guard, index BLOCKED; streaming và chụp orderbook vẫn NOT_IMPLEMENTED. Không có fallback về nguồn đã nghỉ.

READ-ONLY — database read: chỉ đọc nhưng vẫn cần kết nối DB. READ-ONLY — SSI API request: có thể gọi API thật nhưng không dùng Supabase. WRITE: có ghi dữ liệu, bao gồm apply và thay thế phạm vi. UNSUPPORTED: đầu vào hoặc thao tác bị từ chối, không phải kết quả rỗng thành công.
```bash
python main.py stock-eod 19/10/2026 --symbols SSI --data-source ssi_v3
python main.py features-daily --date 19/10/2026 --symbols SSI
python main.py features-intraday --date 19/10/2026 --symbols SSI --timeframes 15m 60m
```

[CLI](../docs/CLI_USAGE.vi.md) · [Scripts](../scripts/README.vi.md)
