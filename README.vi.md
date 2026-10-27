# TradingTPlus — SSI v3

[English](README.md) · [CLI nhanh](docs/CLI_USAGE.vi.md) · [Tham chiếu đầy đủ](docs/CLI_REFERENCE.vi.md)

Trading T+ nghiên cứu cổ phiếu Việt Nam cho T+3–T+5. **Ingest, feature và nghiên cứu là các bước độc lập.** Không có signal/alert/NAV tự chạy sau feature.

## Bắt đầu

Dùng Python 3.11; chạy các lệnh từ **thư mục gốc**. Cần thiết lập SSI và Supabase trong `.env` để ingest, và DB để tính feature. Không commit secret.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp -n .env.example .env
python main.py --help
```

**Không chạy các ví dụ WRITE chỉ để thử tài liệu.** Các ngày và mã bên dưới là ví dụ lịch sử.

## Các lệnh thường dùng

| Việc cần làm | CLI | Loại |
| --- | --- | --- |
| Kiểm tra raw SSI | `python scripts/inspectors/ssi_rest/inspect.py run stock-daily --symbol SSI --date 19/10/2026 --show-mapping` | READ |
| Lấy EOD cổ phiếu | `python main.py stock-eod 19/10/2026 --symbols SSI` | WRITE |
| Backfill cổ phiếu | `python main.py stock-daily-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI` | WRITE |
| Xem index SSI | `python main.py index-preview --date 19/10/2026 --indexes VNINDEX --json` | READ |
| Lấy index | `python main.py index-daily 19/10/2026 --indexes VNINDEX` | WRITE |
| Lấy intraday thử trước | `python main.py stock-intraday 20/10/2026 --symbols SSI` | DRY-RUN |
| Tính daily features | `python main.py features-daily --date 19/10/2026 --symbols SSI` | WRITE |
| Xếp hạng foreign | `python main.py foreign-rank --date 19/10/2026 --ranking accumulation --window 5 --top 20` | READ |
| Lọc cổ phiếu | `python main.py stock-screener --date 19/10/2026 --symbols SSI --version v2` | READ mặc định |

**Đọc [hướng dẫn CLI theo công việc](docs/CLI_USAGE.vi.md)** để xem các lệnh intraday `--write`, backfill intraday, index/foreign features và cách hiểu kết quả. Không chạy `--write` intraday trước khi kiểm tra dry-run/preflight.

## Luồng dữ liệu

`SSI v3 → raw → clean → (kiểm tra chất lượng) → feature riêng → nghiên cứu riêng`.

Stock 1d lấy từ `stock_daily`; intraday 1m được lưu riêng, feature 15m/60m aggregate từ 1m. Tính feature không có nghĩa là tự chạy signal/backtest. Trạng thái raw/clean/feature phải được xác minh riêng.

## Lưu ý quan trọng

- Master phải có sẵn: `init` và `sync-master-data` đã có luồng guard nhưng symbols/securities đã sync có guard ba board, index vẫn BLOCKED. `intraday-ingest` tự động, combined `backfill`, `refill`, `streaming-ingest` hiện tắt.
- Intraday chỉ hỗ trợ pilot thủ công và backfill có guard; mặc định DRY-RUN, chỉ `--write` mới ghi. Completeness chưa xác minh, không giả định 226 nến.
- Exit 0/OK không thay cho kiểm tra completeness. `PARTIAL`, `BLOCKED`, nguồn EMPTY cần kiểm tra.
- Các lệnh `replace`/`rebuild-clean` có thể thay thế dữ liệu feature trong phạm vi chỉ định; đọc reference và kiểm tra DB trước khi dùng.

## Tài liệu chi tiết

[CLI nhanh](docs/CLI_USAGE.vi.md) · [CLI reference đầy đủ](docs/CLI_REFERENCE.vi.md) · [Backfill runbook](docs/backfill/README.vi.md) · [Intraday runbook](docs/STOCK_INTRADAY_PIPELINE.vi.md) · [Scripts](scripts/README.vi.md) · [Kiến trúc](src/README.vi.md) · [Quy ước dữ liệu](docs/DATA_CONVENTIONS.vi.md) · [Trạng thái dự án](docs/CURRENT_STATE.md).

## Kiểm tra offline

```bash
python main.py --help
python -m compileall main.py src scripts tests
python -m pytest -q tests/cli tests/inspectors
```

## Master sync — cập nhật 27/10/2026

`sync-master-data` và alias `init` đã dùng orchestrator có guard, mặc định DRY_RUN. SSI v3 symbols/securities đã hỗ trợ refresh có guard ba board; index_master/index_components giữ BLOCKED. READY chỉ cho refresh không xóa có guard; market completeness authoritative vẫn UNVERIFIED. --write cần đúng một --dataset tường minh và provider READY. Giữ status operator; stock/index mới inactive. Không migration/backfill giá. [Runbook và báo cáo xác minh](src/ingest/master/README.vi.md).
