# SSI REST API Inspector

CLI độc lập này chỉ đọc SSI API, giữ response RAW vừa lấy, đưa chính response đó qua mapping engine dùng chung rồi in CLEAN và diagnostics. Inspector không khởi tạo DB client, không đọc/ghi Supabase và không chạy ingest, feature, signal hay backtest.

## CLI chuẩn theo dataset

```bash
python scripts/ssi_api_inspector/inspect.py run <dataset> [options]

python scripts/ssi_api_inspector/inspect.py run stock-daily --symbol SSI --date 2026-09-08
python scripts/ssi_api_inspector/inspect.py run stock-intraday --symbol SSI --date 2026-09-08
python scripts/ssi_api_inspector/inspect.py run index-daily --index-code VNINDEX --date 2026-09-08
```

Tên dataset không đổi khi đổi nhà cung cấp:

```bash
python scripts/ssi_api_inspector/inspect.py run stock-daily --symbol SSI --date 2026-09-08 --data-source ssi_v2
python scripts/ssi_api_inspector/inspect.py run stock-daily --symbol SSI --from-date 2026-09-01 --to-date 2026-09-08
python scripts/ssi_api_inspector/inspect.py run stock-daily --symbol SSI --date 2026-09-08 --full-json --show-mapping
```

`stock-daily` map vào `stock_daily`; `stock-intraday` map vào `stock_intraday` với `timeframe=1m` cố định; `index-daily` map vào `index_daily`. Dataset cổ phiếu bắt buộc đúng `--symbol`; index bắt buộc đúng `--index-code`. Ưu tiên `YYYY-MM-DD`, vẫn nhận `DD/MM/YYYY`. Chỉ dùng `--date` hoặc đủ cặp from/to có thứ tự; không tự suy đoán ngày.

## Chọn nguồn và routing

Khi không truyền `--data-source`, inspector dùng thứ tự capability registry để chọn nguồn mới nhất đã đăng ký cho dataset. Hiện cả ba dataset chọn **ssi_v3 (preview)**. Preview chỉ dành cho inspector, không có nghĩa dữ liệu đầy đủ, đúng ngữ nghĩa hoặc production-ready. Production chọn nguồn **ready** độc lập và vẫn dùng ssi_v2.

| Dataset CLI | CLEAN contract | ssi_v2 (ready) | ssi_v3 (preview) |
|---|---|---|---|
| `stock-daily` | `stock_daily` | `daily-stock-price` | `securities-summary` |
| `stock-intraday` | `stock_intraday` (1m) | `intraday-ohlc` | `intraday-ohlc` |
| `index-daily` | `index_daily` | `daily-index` | `index-summary` |

Routing lấy từ `inspector.endpoint` trong mapping từng nguồn và được đối chiếu với native endpoint registry trước khi gọi mạng. Không fallback sau lựa chọn rõ ràng hoặc khi thiếu credential, HTTP/API lỗi, response rỗng hay mapping lỗi. Muốn thêm nguồn tương lai cần capability đăng ký, adapter auth/request và mapping/metadata; CLI chuẩn không cần biết tên endpoint nhà cung cấp.

V3 dùng `SSI_API_KEY`/`SSI_API_SECRET`; v2 dùng `SSI_CONSUMER_ID`/`SSI_CONSUMER_SECRET`. Token chỉ ở memory. Help/list không cần credential hoặc network:

```bash
python scripts/ssi_api_inspector/inspect.py --help
python scripts/ssi_api_inspector/inspect.py run --help
python scripts/ssi_api_inspector/inspect.py list
python scripts/ssi_api_inspector/inspect.py list --data-source ssi_v2
```

`list` in capability dataset, trạng thái preview/ready, endpoint routing và danh sách endpoint tương thích của nguồn đang xem.

## Ngày, request plan và paging

Builder giữ contract đã kiểm thử. V2 dùng `FromDate`/`ToDate` dạng `DD/MM/YYYY` và intraday có `resolution=1`. V3 securities summary dùng `from`/`to` chỉ có ngày; intraday OHLC dùng timestamp đầu/cuối ngày và `timeFrame=1m`. Không thêm giờ cho endpoint không yêu cầu.

Ba dataset nhận một ngày hoặc khoảng ngày. Endpoint hỗ trợ range nhận một request range. Do v3 `index-summary` chỉ nhận một ngày, range index được chia thành từng ngày lịch, mỗi ngày có request/context riêng; ngày rỗng giữ `EMPTY`, không tạo row hay kết luận là ngày nghỉ. Kế hoạch trên 100 data request bị chặn trước network. Một request lỗi không chặn các request còn lại, nhưng exit cuối khác 0.

`--page-index`/`--page-size` chỉ lấy đúng một trang ở endpoint hỗ trợ; truyền rõ cho endpoint không paging sẽ bị từ chối. Không có fetch-all. `--limit` chỉ giới hạn sample RAW/CLEAN **mỗi response**. `--full-json` in toàn response đã lấy và CLEAN tương ứng, không tự lấy thêm trang. Report ghi rõ paging và request hiện tại/tổng số.

## RAW, CLEAN và status

```text
yêu cầu chuẩn -> capability/source -> request endpoint -> RAW
              -> mapping source+dataset -> CLEAN + diagnostics -> in
```

Mapping dùng response vừa lấy, không gọi SSI lần hai. RAW giữ field, type và trường lạ, chỉ redact khi hiển thị. CLEAN dùng `definitions.json` và mapping nguồn hiện có, không có contract riêng cho inspector. Field thiếu/chưa xác minh giữ `null` kèm lý do; record malformed, sai identity/date hoặc lỗi chuyển đổi liên kết bằng số thứ tự raw. Lỗi ngoài sample vẫn làm run thất bại. Intraday giữ helper `round(close * volume)` cho value ước tính và không đổi nghĩa volume.

Output gồm dataset; nguồn yêu cầu (`auto` hoặc rõ); nguồn thực tế/trạng thái; endpoint; params/URL đã che; khoảng ngày và request context; HTTP/API status; record count/paging; RAW; CLEAN; mapping version; field thiếu/chưa hỗ trợ/chưa xác minh và lỗi chuyển đổi.

- **PASS:** shape có data và toàn bộ record mapping đạt; không chứng minh completeness hay production-ready.
- **EMPTY:** có data list hợp lệ nhưng rỗng; không chứng minh ngày nghỉ.
- **FAILED:** lỗi tham số/auth/network/HTTP/API/envelope/shape/mapping.
- Exit `0`: không request FAILED; `1`: có ít nhất một FAILED; lỗi argparse: `2`.

Secret trong key, URL, JSON, text và exception được redact/scrub. Redirect bị từ chối; retry và một chu kỳ phục hồi 401 đều hữu hạn.

## Tương thích lệnh endpoint cũ

```bash
python scripts/ssi_api_inspector/inspect.py run securities-summary --symbol SSI --date 2026-09-08
python scripts/ssi_api_inspector/inspect.py run daily-stock-price --data-source ssi_v2 --symbol SSI --date 2026-09-08
python scripts/ssi_api_inspector/inspect.py run daily-ohlc --symbol SSI --date 2026-09-08
python scripts/ssi_api_inspector/inspect.py run all --symbol SSI --board HOSE --index-code VNINDEX --date 2026-09-08
```

Alias không làm `run all` gọi trùng native endpoint; tập endpoint và hành vi `run all` được giữ nguyên. `daily-ohlc` chỉ đối chiếu RAW, không phải canonical `stock_daily`. Endpoint danh mục/auth và option riêng vẫn tồn tại.

## Giới hạn kiểm chứng

Test/fixture offline chỉ kiểm tra orchestration, request shape, giữ RAW và mapping; không chứng minh response live, entitlement, availability hay completeness của SSI. Trạng thái live là **NOT_RUN / UNVERIFIED** trừ khi báo cáo cụ thể ghi khác. Chỉ smoke live read-only khi credential đã có sẵn và dùng ngày/mã rõ ràng. Không có migration, DB impact hoặc backfill.
