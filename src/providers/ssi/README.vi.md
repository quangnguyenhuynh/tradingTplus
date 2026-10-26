# src/providers/ssi

Hợp đồng provider và registry SSI v3. Chỉ Stock Daily và Index Daily sẵn sàng production; không có v2 hoặc fallback.


## Pilot intraday thủ công có guard

`stock-intraday` hỗ trợ đúng một mã và ngày giao dịch Việt Nam tường minh. Mặc định/`--dry-run` là READ-ONLY; chỉ `--write` mới cho phép chuỗi chèn raw → clean có kiểm soát. Cần credential SSI; credential service Supabase cho phép preflight chỉ đọc eligibility/xung đột và bắt buộc khi ghi. Nếu chưa cấu hình DB, dry-run báo `NOT_RUN_NO_CREDENTIALS`, số dự kiến chưa biết và `write_ready=false`.

```bash
python main.py stock-intraday 20/10/2026 --symbols SSI
python main.py stock-intraday 20/10/2026 --symbols SSI --write
```

Lệnh thứ hai **chỉ dành cho chủ sở hữu sau khi kiểm tra dry-run/preflight**. Không nhận khoảng ngày, ALL/wildcard, scope thiếu, nhiều mã hoặc ngày tương lai. Cả hai status trong master phải active. Chỉ nguồn `ssi_v3`, timeframe `1m`; value canonical giữ chính xác `ohlc.value`, thiếu/sai sẽ chặn pilot và không ước tính bù. Hàng giống giữ nguyên; clean khác giá trị hoặc raw xung đột key/source/payload sẽ chặn. Không force overwrite. Xác nhận raw trước clean; ghi dở dang/không rõ kết quả trả exit khác 0, cần kiểm tra đúng scope rồi chạy lại an toàn. Không cam kết transaction xuyên hai bảng. Completeness vẫn UNVERIFIED. Các lệnh ingest/backfill/refill/streaming intraday khác và schedule vẫn tắt. Pilot không chạy feature/signal/backtest.

Xem [runbook](../../../docs/STOCK_INTRADAY_PIPELINE.vi.md) về thứ tự ghi, idempotency, partition, phục hồi và xác minh của chủ sở hữu. Inspector vẫn hoàn toàn chỉ đọc; registry giữ preview, không có factory production chung.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `base.py`
- `capabilities.py`
- `registry.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.

## Triển khai capability trong tương lai

Intraday: adapter preview đã được tái sử dụng cho pilot thủ công cô lập. Registry vẫn preview, factory production chung vẫn không có. Không bật ingest tự động/schedule/backfill; xem runbook về guard, provenance và hạn chế completeness.

Master: triển khai adapter/mapping riêng trong `providers/ssi/adapters` và service ở `ingest/master`; giữ status do operator điều khiển, không suy luận danh sách mã từ lịch sử giá, không sync master ngầm trong ingest.

Streaming: cần protocol và cơ chế xác thực được kiểm chứng riêng ở `ingest/streaming`; decoder payload lịch sử không chứng minh tính tương thích v3. Chỉ khôi phục lịch sau khi capability được kiểm chứng.

SSI v4 tương lai: thêm client, adapter theo DataSourceAdapter/AdapterResult, mapping JSON có version và entry registry theo dataset. Adapter cung cấp source của raw; chỉ đánh dấu ready sau fixture/semantic tests. Không đổi logic ingest và không fallback. Task này không triển khai v4.

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

## Registry master

Contract/registry master tách khỏi readiness daily/intraday. Cả bốn dataset SSI v3 BLOCKED; không triển khai v4/v5 giả, chưa xác minh field master. [Contract, cách thêm version và audit](../../ingest/master/README.vi.md).
