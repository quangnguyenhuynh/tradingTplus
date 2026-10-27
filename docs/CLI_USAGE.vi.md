# TradingTPlus CLI — Hướng dẫn nhanh

[English](CLI_USAGE.md) · [Tham chiếu đầy đủ](CLI_REFERENCE.vi.md) · [Trang chủ](../README.vi.md)

Chạy lệnh từ **thư mục gốc repo**, sử dụng Python 3.11 và cấu hình SSI/Supabase phù hợp. Ngày ví dụ chỉ minh họa (19–21/10/2026), không phải lệnh bắt buộc chạy hôm nay.

**Quy ước:** `READ` chỉ đọc API/DB; `WRITE` ghi DB; `DRY-RUN` kiểm tra không ghi; `UNAVAILABLE` chưa được hỗ trợ. Mỗi lệnh là **bước độc lập**: ingest không tự chạy feature, screener, signal hoặc backtest.

## Tôi muốn làm gì?

| Công việc | Lệnh chính | Tác động |
| --- | --- | --- |
| Xem dữ liệu SSI trước khi ingest | `scripts/inspectors/ssi_rest/inspect.py run stock-daily` | READ (SSI) |
| Lấy EOD cổ phiếu | `stock-eod` | WRITE raw/clean, kiểm tra completeness daily |
| Backfill EOD cổ phiếu | `stock-daily-backfill` | WRITE raw/clean |
| Xem EOD chỉ số | `index-preview` | READ (SSI) |
| Lấy / backfill EOD chỉ số | `index-daily` / `index-daily-backfill` | WRITE raw/clean |
| Lấy intraday 1m thủ công | `stock-intraday` | DRY-RUN mặc định; `--write` ghi DB |
| Backfill intraday có giới hạn | `stock-intraday-backfill` | DRY-RUN mặc định; `--write` ghi DB |
| Tính feature cổ phiếu daily / intraday | `features-daily` / `features-intraday` | WRITE features |
| Tính / kiểm tra feature khối ngoại | `foreign-features-daily` / `foreign-features-preview` | WRITE / READ |
| Xem dòng tiền khối ngoại | `foreign-rank` | READ (DB) |
| Tính feature chỉ số | `index-features-daily` | WRITE features |
| Lọc cổ phiếu | `stock-screener` | READ mặc định; tùy chọn apply có thể ghi |

## 1. Xem nguồn trước khi ghi

**READ — gọi SSI, không ghi DB:**

```bash
python scripts/inspectors/ssi_rest/inspect.py run stock-daily --symbol SSI --date 19/10/2026 --show-mapping
python main.py index-preview --date 19/10/2026 --indexes VNINDEX --json
```

## 2. Lấy dữ liệu EOD

**WRITE — ghi raw/clean.** Master mã/index phải tồn tại; `init` và `sync-master-data` có luồng guard nhưng symbols/securities đã hỗ trợ; index còn BLOCKED. Bỏ `--data-source` để dùng nguồn mặc định sẵn sàng (SSI v3); không truyền `auto`.

```bash
# Một ngày, một hoặc nhiều cổ phiếu
python main.py stock-eod 19/10/2026 --symbols SSI HPG

# Backfill nhiều ngày
python main.py stock-daily-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI HPG

# Index EOD và backfill
python main.py index-daily 19/10/2026 --indexes VNINDEX
python main.py index-daily-backfill --from 01/10/2026 --to 19/10/2026 --indexes VNINDEX
```

`daily` không hoàn toàn giống `stock-eod` về default ngày và completeness; xem [reference](CLI_REFERENCE.vi.md) trước khi dùng.

## 3. Lấy intraday 1m thủ công

**Chỉ operator; luôn chạy DRY-RUN rồi đọc preflight trước khi chọn WRITE.** Một ngày chỉ nhận **một mã**; backfill yêu cầu mã/ngày cụ thể và tối đa **50 cặp mã × ngày trong tuần**. Không có ingest intraday tự động. Completeness vẫn chưa được xác minh; không lấy 226 nến làm chuẩn cố định.

```bash
# Kiểm tra trước (không ghi)
python main.py stock-intraday 20/10/2026 --symbols SSI
python main.py stock-intraday-backfill --from 19/10/2026 --to 21/10/2026 --symbols SSI --dry-run

# Chỉ chạy khi preflight xác nhận điều kiện an toàn
python main.py stock-intraday 20/10/2026 --symbols SSI --write
python main.py stock-intraday-backfill --from 19/10/2026 --to 21/10/2026 --symbols SSI --write
```

Lỗi/partial write cần đối chiếu raw và clean theo đúng mã/ngày trước khi chạy lại; xem [runbook phục hồi](backfill/README.vi.md).

## 4. Tính feature — chạy RIÊNG sau khi kiểm chứng clean data

**WRITE — feature**, không tự ingest hay gọi downstream. Daily 1d lấy từ `stock_daily`; intraday 15m/60m tính từ 1m đã lưu. Không coi ingest OK là chứng minh completeness.

```bash
python main.py features-daily --date 19/10/2026 --symbols SSI
python main.py features-daily --from 01/10/2026 --to 19/10/2026 --symbols SSI
python main.py features-intraday --date 19/10/2026 --symbols SSI --timeframes 15m 60m
python main.py index-features-daily --date 19/10/2026 --indexes VNINDEX
```

`--mode replace` và `--mode rebuild-clean` có thể **xóa và ghi lại feature trong phạm vi chọn**; không đưa vào luồng thao tác nhanh. Đọc [reference](CLI_REFERENCE.vi.md) trước khi dùng.

## 5. Foreign, screener và nghiên cứu

```bash
# READ — xem nguồn foreign và xếp hạng
python main.py foreign-features-preview --symbol SSI --date 19/10/2026 --show-source
python main.py foreign-rank --date 19/10/2026 --ranking accumulation --window 5 --top 20

# DRY-RUN / WRITE — tính feature foreign
python main.py foreign-features-daily --date 19/10/2026 --symbols SSI --dry-run
python main.py foreign-features-daily --date 19/10/2026 --symbols SSI

# READ mặc định — screener
python main.py stock-screener --date 19/10/2026 --symbols SSI --version v2
```

Historical Analog là nhánh nghiên cứu có gate riêng, **không tự tạo signal/alert/NAV**. Xem [tài liệu Analog](../src/research/analogs/README.vi.md).

## 6. Help và xử lý kết quả

```bash
python main.py --help
python main.py stock-eod --help
python main.py features-daily --help
python main.py stock-intraday-backfill --help
```

- Ngày các lệnh ví dụ phần lớn dùng `DD/MM/YYYY` (nhiều lệnh còn hỗ trợ `YYYY-MM-DD`); tham số và kiểu ngày khác nhau tùy domain. Mã cổ phiếu dùng **khoảng trắng** sau `--symbols`; riêng `index-preview` dùng chuỗi mã phân tách bằng **dấu phẩy**.
- **Exit 0 không luôn nghĩa là dữ liệu đầy đủ**: xem status, count, warnings và check raw/clean. `PARTIAL`, `BLOCKED` hoặc API EMPTY cần xem kỹ.
- Các lệnh `intraday-ingest`, `backfill` (combined), `refill`, `streaming-ingest` hiện **UNAVAILABLE**; có `--help` không có nghĩa là chạy được.
- Các tên cũ `backfill-daily`, `backfill-intraday`, `index-backfill` vẫn tương thích, nhưng hướng dẫn này dùng tên canonical.

## Chi tiết kỹ thuật

[Toàn bộ CLI, tham số, alias, status và recovery](CLI_REFERENCE.vi.md) · [Runbook intraday](STOCK_INTRADAY_PIPELINE.vi.md) · [Backfill](backfill/README.vi.md) · [Scripts](../scripts/README.vi.md) · [Quy ước dữ liệu](DATA_CONVENTIONS.vi.md).

## Master sync — cập nhật 27/10/2026

`sync-master-data` và alias `init` đã dùng orchestrator có guard, mặc định DRY_RUN. SSI v3 symbols/securities đã hỗ trợ refresh có guard ba board; index_master/index_components giữ BLOCKED. READY chỉ cho refresh không xóa có guard; market completeness authoritative vẫn UNVERIFIED. --write cần đúng một --dataset tường minh và provider READY. Giữ status operator; stock/index mới inactive. Không migration/backfill giá. [Runbook và báo cáo xác minh](../src/ingest/master/README.vi.md).

## Cutover master hợp nhất — 27/10/2026

Phần này thay thế hướng dẫn cũ sync symbols/securities độc lập: chỉ symbols là đích vật lý; securities là alias deprecated có warning, all chỉ chạy symbols một lần. Owner apply A expand/merge TRƯỚC deploy app; B retire riêng có approval, mặc định abort. Agent không apply production. VN50 GROWTH được loại đúng rule và đếm; HNX-request DERIVATIVES/Future giữ domain thật và inactive mặc định. Index vẫn BLOCKED; không backfill giá. [Runbook](../src/ingest/master/README.vi.md).
