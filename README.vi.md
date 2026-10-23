# TradingTPlus — SSI v3

Tên CLI canonical và alias tương thích (không có lịch bỏ alias): `stock-daily-backfill` → `backfill-daily`. Chỉ tên CLI thay đổi; runner, tham số, flow JSON và exit code giữ nguyên. Stock Daily/Index Daily backfill ACTIVE / WRITE; Stock Intraday backfill DISABLED / NOT_IMPLEMENTED, tách biệt manual pilot.

[English](README.md)

Trading T+ nghiên cứu cổ phiếu Việt Nam cho khoảng nắm giữ T+3–T+5 phiên. Phase 0 đã đóng COMPLETE_WITH_NOTES; Phase 1 là Historical Analog EOD cùng mã/checkpoint. Kết quả nghiên cứu chưa tự tạo tín hiệu, alert hay phân bổ NAV.

## Kiến trúc

`main.py → src/cli → src/ingest` điều phối ingest. `src/providers/ssi` chọn client/adapter v3; `src/contracts` map/validate contract, `src/quality` kiểm tra chất lượng. `src/database` giữ persistence raw/clean riêng. `src/features/{stock,foreign,index}` đọc clean độc lập; `src/research/{screener,analogs}` là tầng nghiên cứu sau feature. Ingest không tự tính feature hay chạy nghiên cứu.

## Cài đặt và cấu hình

Dùng Python 3.11 như CI. Cài dependency runtime và pytest riêng. Chỉ sao chép `.env.example` khi tạo cấu hình local mới; điền credential tại máy, không commit. `src/config.py` đọc `.env` bằng python-dotenv.

| Công việc | Credential SSI | Credential DB |
| --- | --- | --- |
| Ingest/backfill daily | `SSI_API_KEY`, `SSI_API_SECRET` | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` phía server |
| REST inspector / index-preview | Cặp SSI trên | Không cần |
| Feature, kiểm tra DB, RPC foreign, screener, Analog dùng DB | Không cần | URL Supabase và key phía server |
| Help, inspector list, xem config, đăng ký profile Analog dry-run | Không cần | Không cần |
| Kiểm tra catalog PostgreSQL | Không cần | `PHASE0_DATABASE_URL` |

DB client dùng `SUPABASE_URL` và `SUPABASE_SERVICE_KEY`; `SUPABASE_KEY` vẫn là trường cấu hình nhưng không phải fallback trong client này. Dùng service key cho thao tác server và atomic replace. Schema/RPC của domain phải được triển khai trước. Task tài liệu này không apply migration.
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install pytest
```

## Khả năng hiện tại

Đối chiếu commit `b5cb3276` trên `dev` (PR #178). Chạy tại thư mục gốc repository. Ngày và mã trong ví dụ chỉ minh họa; kiểm tra nguồn và chọn đúng phạm vi trước khi chạy. Chỉ kiểm tra cú pháp offline, chưa gọi SSI hay Supabase thật.

Ingest Stock Daily (`securitiesSummary`) và Index Daily (`indexSummary`) qua SSI v3: ACTIVE. Feature stock, foreign và index: ACTIVE trên dữ liệu clean đã lưu. Screener và Historical Analog: RESEARCH_ACTIVE. Intraday có pilot thủ công đúng một mã/ngày (chỉ đọc nếu không có `--write`); intraday tự động, đồng bộ master, streaming và chụp orderbook vẫn NOT_IMPLEMENTED. Xem [runbook thủ công](docs/STOCK_INTRADAY_PIPELINE.vi.md). Không có fallback về nguồn đã nghỉ.

READ-ONLY — database read: chỉ đọc nhưng vẫn cần kết nối DB. READ-ONLY — SSI API request: có thể gọi API thật nhưng không dùng Supabase. WRITE: có ghi dữ liệu, bao gồm apply và thay thế phạm vi. UNSUPPORTED: đầu vào hoặc thao tác bị từ chối, không phải kết quả rỗng thành công.

## Bắt đầu và vận hành thường gặp

Bắt đầu bằng preview SSI chỉ đọc. Ingest cần master đã có: đồng bộ master đang tắt nên cài mới không thể tự khởi tạo bằng `init`. Sau khi xác minh summary ingest, tính feature bằng lệnh riêng. Mỗi lệnh dưới đây độc lập; dừng đọc kết quả trước khi tiếp tục.

Preview: READ-ONLY — SSI API request. Stock EOD: WRITE — raw/clean ingest. Daily feature: WRITE — feature calculation. Screener mặc định: READ-ONLY — database read. Không chạy các lệnh ghi chỉ để thử tài liệu.
```bash
python scripts/inspectors/ssi_rest/inspect.py run stock-daily --symbol SSI --date 19/10/2026 --show-mapping
python main.py stock-eod 19/10/2026 --symbols SSI --data-source ssi_v3
python main.py features-daily --date 19/10/2026 --symbols SSI
python main.py stock-screener --date 19/10/2026 --symbols SSI --version v2
```

```bash
python main.py stock-daily-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI
python main.py index-preview --date 19/10/2026 --indexes VNINDEX --json
python main.py foreign-rank --date 19/10/2026 --ranking accumulation --window 5 --symbols SSI --top 20
python main.py analogs profiles register --profile TPLUS_ANALOG_CORE_EOD --version 1
```

Các ví dụ ghi có thể cập nhật raw/clean/feature nếu chạy thật. Chọn đúng scope, đọc summary trước khi chạy bước sau. Exit 0 có thể PARTIAL/blocked; không chứng minh completeness. Master phải có sẵn vì init/sync hiện tắt. Replace/rebuild-clean có thể xóa và ghi lại đúng scope feature; đọc hướng dẫn an toàn trước.

## Tài liệu chuyên sâu

- [CLI](docs/CLI_USAGE.vi.md)
- [Scripts](scripts/README.vi.md)
- [SSI REST inspector](scripts/inspectors/ssi_rest/README.vi.md)
- [Architecture / domain map](src/README.vi.md)
- [Stock features](src/features/stock/README.vi.md)
- [Foreign EOD](docs/FOREIGN_EOD_FEATURES.vi.md)
- [Index features](src/features/index/README.vi.md)
- [Historical Analog](src/research/analogs/README.vi.md)
- [Screener](src/research/screener/README.vi.md)
- [Data conventions](docs/DATA_CONVENTIONS.vi.md)
- [Current state](docs/CURRENT_STATE.md)

## Kiểm tra offline

```bash
python main.py --help
python -m compileall main.py src scripts tests
python -m pytest -q tests/cli tests/inspectors
```

Task tài liệu không thay schema, dữ liệu, migration hay yêu cầu backfill; không chạy ví dụ ghi để thử tài liệu.

Nếu chưa có .env local, sao chép mẫu mà không ghi đè cấu hình hiện có:

```bash
cp -n .env.example .env
```
