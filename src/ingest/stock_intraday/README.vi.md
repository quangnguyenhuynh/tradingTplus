# src/ingest/stock_intraday

Tên CLI canonical và alias tương thích (không có lịch bỏ alias): `stock-intraday-backfill` → `backfill-intraday`. Chỉ tên CLI thay đổi; runner, tham số, flow JSON và exit code giữ nguyên. Stock Daily/Index Daily backfill ACTIVE / WRITE; Stock Intraday backfill DISABLED / NOT_IMPLEMENTED, tách biệt manual pilot.

[English](README.md)


## Pilot intraday thủ công có guard

`stock-intraday` hỗ trợ đúng một mã và ngày giao dịch Việt Nam tường minh. Mặc định/`--dry-run` là READ-ONLY; chỉ `--write` mới cho phép chuỗi chèn raw → clean có kiểm soát. Cần credential SSI; credential service Supabase cho phép preflight chỉ đọc eligibility/xung đột và bắt buộc khi ghi. Nếu chưa cấu hình DB, dry-run báo `NOT_RUN_NO_CREDENTIALS`, số dự kiến chưa biết và `write_ready=false`.

```bash
python main.py stock-intraday 20/10/2026 --symbols SSI
python main.py stock-intraday 20/10/2026 --symbols SSI --write
```

Lệnh thứ hai **chỉ dành cho chủ sở hữu sau khi kiểm tra dry-run/preflight**. Không nhận khoảng ngày, ALL/wildcard, scope thiếu, nhiều mã hoặc ngày tương lai. Cả hai status trong master phải active. Chỉ nguồn `ssi_v3`, timeframe `1m`; value canonical giữ chính xác `ohlc.value`, thiếu/sai sẽ chặn pilot và không ước tính bù. Hàng giống giữ nguyên; clean khác giá trị hoặc raw xung đột key/source/payload sẽ chặn. Không force overwrite. Xác nhận raw trước clean; ghi dở dang/không rõ kết quả trả exit khác 0, cần kiểm tra đúng scope rồi chạy lại an toàn. Không cam kết transaction xuyên hai bảng. Completeness vẫn UNVERIFIED. Các lệnh ingest/backfill/refill/streaming intraday khác và schedule vẫn tắt. Pilot không chạy feature/signal/backtest.

Xem [runbook](../../../docs/STOCK_INTRADAY_PIPELINE.vi.md) về thứ tự ghi, idempotency, partition, phục hồi và xác minh của chủ sở hữu. Inspector vẫn hoàn toàn chỉ đọc; registry giữ preview, không có factory production chung.

## Các lệnh tạm tắt

Bảy lệnh dưới giữ parser nhưng dừng trước khi nạp handler hoặc tạo client SSI/DB. Trả exit 1 và JSON status FAILED, error_type NOT_IMPLEMENTED. Source tường minh bị từ chối có thể trả exit 2 ở preflight trước đó. Help vẫn mô tả mục đích cũ, không chứng minh khả năng chạy.

| Lệnh | Mục đích trước đây | Adapter / dataset cần trong tương lai |
| --- | --- | --- |
| sync-master-data, init | Đồng bộ master idempotent | Adapter master v3 được xác minh, giữ status operator; master |
| intraday-ingest | Ingest raw/clean nguồn 1m | Adapter v3 1m, pagination, timestamp, đơn vị đã xác minh; stock_intraday |
| stock-intraday-backfill | Lịch sử nguồn 1m | Cùng adapter; stock_intraday |
| backfill | Daily/intraday kèm check | Cùng adapter; stock_intraday; không chạy riêng phần daily |
| refill | Nguồn/check/feature một mã | Cùng adapter; stock_intraday; không chạy riêng daily/feature |
| streaming-ingest | Streaming giới hạn, ghi tùy chọn | Adapter protocol/auth/capture v3 đã xác minh; streaming |

Chụp orderbook cũng tắt đến khi có adapter streaming được xác minh; không tự tạo endpoint REST depth công khai. Raw/clean/master/feature/streaming lịch sử vẫn còn và dùng được theo contract. Gọi lệnh đang tắt không fallback, xóa hay sửa lịch sử. Dưới đây chỉ là help, không phải ví dụ chạy production thành công.

```bash
python main.py init --help
python main.py sync-master-data --help
python main.py intraday-ingest --help
python main.py stock-intraday --help
python main.py stock-intraday-backfill --help
python main.py backfill --help
python main.py refill --help
python main.py streaming-ingest --help
```
## Feature kỹ thuật cổ phiếu

Cả ba route đều WRITE — feature calculation vào `stock_features`, khóa `(symbol,timeframe,time)`. Không cần credential SSI. `1d` đọc `stock_daily`; `15m`, `60m` aggregate clean 1m `stock_intraday` trong bộ nhớ cùng ngữ cảnh giá daily. Chỉ persist bucket đã đóng. `stock_intraday` vẫn chỉ lưu 1m. Không hỗ trợ persist feature `1m`, `5m`. Tắt ingest nguồn không ngăn tính feature trên lịch sử intraday đã có.

`features` là router tương thích: tùy chọn `--date`, `--mode incremental|full` (mặc định incremental), mã tùy chọn, timeframe mặc định `15m 60m 1d`; không có range/replace. `features-daily` luôn chọn 1d. `features-intraday` mặc định `15m 60m`, hỗ trợ `--as-of` dạng `HH:MM` giờ Việt Nam hoặc timestamp có timezone. Không ghép as-of với khoảng ngày. Hai route tách nguồn bắt buộc ngày đích, cặp khoảng ngày hoặc full mode.

Incremental dùng watermark riêng mỗi stream và warm-up giới hạn (daily năm năm; intraday 250 phiên quan sát, không phải ngày lịch). Không có đầu ra mới có thể là OK không làm gì. Khoảng ngày chạy backfill bao gồm hai đầu. Full tính lại/upsert lịch sử đã chọn, không xóa; có thể tốn nhiều RAM, không ghép ngày/range. Sửa dữ liệu nguồn không tự vô hiệu feature cũ.

**WRITE — explicit rebuild có thể phá hủy dữ liệu:** replace và rebuild-clean cùng thay thế atomic một phạm vi. Bắt buộc đúng một mã, một timeframe được persist và hai đầu khoảng; không wildcard/ALL, không `--date`. Tính/validate bộ thay thế không rỗng trước, sau đó RPC service-role hiện có xóa và ghi lại đúng phạm vi. Xác nhận nguồn/warm-up đủ, đối soát mẫu, lưu bằng chứng trước/sau trước khi chạy. Không có cờ dry-run. Replace intraday phải chỉ định đúng một timeframe; mặc định hai timeframe bị từ chối.

```bash
python main.py features --help
python main.py features-daily --help
python main.py features-intraday --help
python main.py features --date 19/10/2026 --symbols SSI HPG --timeframes 1d
python main.py features-daily --date 19/10/2026 --symbols SSI
python main.py features-daily --from 01/10/2026 --to 19/10/2026 --symbols SSI
python main.py features-daily --mode full --symbols SSI
python main.py features-intraday --date 19/10/2026 --symbols SSI --timeframes 15m 60m --as-of 14:30
python main.py features-intraday --from 01/10/2026 --to 19/10/2026 --symbols SSI --timeframes 60m
python main.py features-daily --mode replace --symbols SSI --from 01/10/2026 --to 19/10/2026
python main.py features-intraday --mode rebuild-clean --symbols SSI --timeframes 15m --from 01/10/2026 --to 19/10/2026
```

[CLI](../../../docs/CLI_USAGE.vi.md)

## Preview intraday SSI v3 nhiều trang (chỉ đọc)

Route `stock-intraday`/native `intraday-ohlc` của REST inspector nay dùng adapter preview chung và tải mọi trang từ trang bắt đầu đến kết thúc tường minh hoặc lỗi/giới hạn. `--limit` chỉ giới hạn in; `--full-json` bao gồm mọi trang raw đã nhận và clean candidate. `--max-pages` mặc định 100 (1–1000); chạm giới hạn, trang lặp, total không khớp hay lỗi request trả FAILED/exit 1 và giữ bằng chứng đã nhận. Không đổi các route daily/index/catalog một-trang của inspector.

Mẫu SSI live do chủ sở hữu cung cấp cho 2026-10-20 xác nhận `ohlc.tradingDate` dạng `YYYY/MM/DD HH:mm:ss`, field `ohlc.value` và terminal `{"code":204,"msg":"No Content"}`. Diễn giải tường minh đúng format nguồn này theo `Asia/Ho_Chi_Minh`, rồi chuyển UTC; vẫn hỗ trợ dạng có offset hợp lệ. Alias `time` cũ vẫn bắt buộc timezone. Từ chối chỉ ngày/chỉ giờ và dạng naive khác; không tạo ngày từ request hay dịch phút.

Canonical v3 `value` là **SSI-reported intraday candle value** (giá trị nến intraday SSI trả về), parse chính xác số nguyên không âm trong signed BIGINT, không qua float. **Không ước tính hoặc tính bù**. Nguồn thiếu/null/rỗng giữ NULL kèm SOURCE_VALUE_MISSING; sai định dạng/không hữu hạn/lẻ/âm/tràn bị từ chối. Zero giữ nguyên zero. Report tách nguồn có value, numeric hợp lệ, mapping giữ nguyên và xác minh độc lập ý nghĩa thị trường (vẫn false).

Envelope 204/No Content đã xác nhận chỉ kết thúc paging OHLC 1m khi không có payload/marker lỗi mâu thuẫn và đã qua kiểm tra metadata/số đếm. Giữ nguyên raw envelope, termination provider_no_content_204. Trang ngắn không rỗng không tự kết thúc; trang lặp, total sai, malformed/lỗi và cắt cụt do giới hạn vẫn fail. --limit chỉ giới hạn in; --full-json giữ các trang raw đã nhận, candidate và diagnostic.

Ngày được cung cấp có 226 hàng unique trên 23 trang không rỗng rồi trang 24, thứ tự giảm dần, 135 nến sáng/90 chiều/một nến 14:45. Đây là quan sát do chủ sở hữu báo cho riêng ngày đó, không phải số count hay công thức chung. Chỉ có hai object candle thật và terminal envelope được cung cấp; replay offline xác minh 2/2, không tái tạo các hàng còn thiếu. Agent live rerun: NOT_RUN (thiếu credential). Bar-start/end, ý nghĩa value/turnover độc lập và completeness thị trường còn chưa xác minh. Ingest tự động/schedule vẫn tắt; inspector preview không đọc/ghi DB. Pilot thủ công riêng được mô tả phía trên.

Xem [runbook và checklist](../../../docs/STOCK_INTRADAY_PIPELINE.vi.md) để biết mapping từng field, paging, validation/session/gap, giới hạn nguồn và cách promotion riêng.

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --from-date 2026-10-01 --to-date 2026-10-19 --page-size 100 --max-pages 100 --limit 5
python scripts/inspectors/ssi_rest/inspect.py run intraday-ohlc --symbol SSI --date 2026-10-19 --ascending --limit 5
```

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --page-size 10 --max-pages 100 --limit 5
```
