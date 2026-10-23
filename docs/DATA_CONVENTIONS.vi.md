# Quy ước dữ liệu

## Mục đích

Tài liệu này định nghĩa các quy ước dữ liệu cho TradingTPlus trong Phase 0. Mục
tiêu là bảo vệ độ đúng của dữ liệu raw/clean và hướng dẫn công việc sau này về
feature, signal, backtest, kiểm tra completeness và alert. Các quy ước mô tả ý
nghĩa dữ liệu; chúng không cho phép thay đổi schema hoặc ghi lại dữ liệu.

## Nguồn sự thật

- Dữ liệu raw giữ payload SSI/API và thông tin truy vết ingest.
- Dữ liệu clean chứa các dòng đã normalize cho nghiên cứu và feature pipeline.
- `stock_daily` là nguồn daily chuẩn cho feature `1d`.
- `stock_intraday` chỉ lưu nến clean `1m`.
- Timeframe intraday cao hơn như `5m`, `15m`, `60m` được tạo từ
  `stock_intraday` trong bước tính feature.
- Không tạo feature `1d` chuẩn bằng cách aggregate nến intraday.

## Quy ước thời gian và múi giờ

- Dùng `Asia/Ho_Chi_Minh` để diễn giải phiên thị trường Việt Nam và hiển thị giờ
  giao dịch cho người dùng.
- PostgreSQL/Supabase có thể hiển thị giá trị `timestamptz` theo UTC. Việc hiển
  thị UTC không có nghĩa thời gian nến bị sai.
- `stock_intraday.time` là timestamp thị trường/nến.
- `stock_intraday.time` là nguồn sự thật cho thứ tự intraday, aggregation,
  completeness, feature, signal, backtest và live alert.
- `2026-07-15T02:15:00+00:00` tương đương
  `2026-07-15 09:15:00 Asia/Ho_Chi_Minh`.
- Luôn giữ timestamp có timezone. Không chuyển thành datetime naive.
- Không lưu timestamp thị trường thành text chỉ để hình thức hiển thị giống giờ
  Việt Nam.
- Không cộng thủ công bảy giờ. Hãy chuyển đổi timezone.

Ví dụ chuyển đổi đúng bằng pandas:

```python
time_utc = pd.to_datetime(df["time"], utc=True)
time_vn = time_utc.dt.tz_convert("Asia/Ho_Chi_Minh")
```

Dùng timestamp Việt Nam đã chuyển đổi để xác định ngày giao dịch, phân loại
phiên, hiển thị giờ giao dịch hoặc áp dụng ranh giới phiên. Khi contract của
pipeline yêu cầu UTC, giữ timestamp UTC có timezone để lưu trữ, so sánh và
serialize ổn định.

## Timestamp thị trường và timestamp audit

Timestamp thị trường cho biết dữ liệu thị trường áp dụng tại thời điểm nào.
Timestamp audit cho biết ứng dụng fetch, nhận, tạo, cập nhật hoặc tính một dòng
tại thời điểm nào. Hai nhóm này không thể thay thế nhau.

| Cột | Ý nghĩa | Cách dùng hợp lệ đối với thời gian thị trường |
| --- | --- | --- |
| `stock_intraday.time` | Timestamp thị trường/nến intraday | Thứ tự, aggregation, completeness, feature, signal, backtest và alert |
| `created_at` | Thời điểm ứng dụng insert lần đầu | Chỉ audit |
| `updated_at` | Thời điểm application upsert gần nhất | Chỉ audit |
| `fetched_at` | Thời điểm fetch raw | Chỉ truy vết ingest |
| `received_at` | Thời điểm nhận/capture streaming | Chỉ audit transport/capture; không thay thế timestamp thị trường từ nguồn |
| `last_updated_at` | Thời điểm tính/upsert feature | Chỉ audit độ mới của feature |

Không suy ra thứ tự nến, ngày giao dịch, nến aggregate, thời điểm signal, điểm
vào/ra backtest hoặc giờ thị trường của alert từ timestamp audit. Retry hoặc
backfill trễ có thể làm timestamp audit muộn hơn nhiều so với sự kiện thị trường.

## Ngày giao dịch, phiên và aggregation

- Xác định ngày giao dịch theo `Asia/Ho_Chi_Minh`, không chỉ dựa vào ngày UTC.
- Ngày trong tuần không chứng minh có phiên giao dịch; phải xử lý rõ holiday,
  halt, phiên rút ngắn, auction và response nguồn bị thiếu.
- Tạo timeframe intraday cao hơn từ nến clean `stock_intraday` `1m`.
- Không aggregate xuyên ngày giao dịch Việt Nam, ranh giới phiên hoặc giờ nghỉ
  trưa.
- Phải định nghĩa timestamp của nến aggregate là đầu hay cuối nến trước khi sử
  dụng và áp dụng nhất quán.
- Tính toán live/alert phải dùng nến đã đóng hoặc đánh dấu rõ nến chưa hoàn tất.

## Dữ liệu thiếu và không hợp lệ

- Không tạo dòng giả cho cuối tuần, ngày lễ, response rỗng hoặc endpoint không
  được hỗ trợ.
- Không âm thầm thay giá, volume, value hoặc flow bị thiếu bằng 0.
- Không forward-fill OHLCV trừ khi có contract nghiên cứu yêu cầu rõ ràng.
- Parse timestamp nguồn một cách tường minh. Reject hoặc quarantine timestamp
  không hợp lệ; không thay bằng thời gian hiện tại hay timestamp audit.
- Đánh giá completeness theo symbol, ngày giao dịch Việt Nam, phiên dự kiến và
  source/timeframe. Không có một số lượng nến cố định áp dụng cho mọi trường hợp.

## Đơn vị và nguồn gốc

Ghi nhận và giữ rõ field do sàn cung cấp hay được suy ra. Không nhầm volume từng
nến với volume lũy kế và không so sánh các value khác đơn vị khi chưa normalize.

Theo nguồn: SSI v3 intraday preview dùng trực tiếp `ohlc.value`, parse chính xác BIGINT, không tính bù từ close/volume; thiếu/null giữ NULL và cảnh báo, sai thì từ chối. Các hàng lịch sử và caller legacy có thể dùng `round(close * volume)` như ước tính; không relabel hay sửa lại. Ý nghĩa turnover của field SSI chưa được chứng nhận độc lập.

## Checklist sử dụng downstream

Trước khi làm completeness, feature, signal, backtest hoặc live alert:

1. Dùng đúng bảng chuẩn và timestamp thị trường.
2. Parse timestamp có timezone và chuyển sang `Asia/Ho_Chi_Minh` cho logic ngày
   giao dịch/phiên.
3. Không dùng timestamp audit làm trình tự thời gian thị trường.
4. Tôn trọng ranh giới symbol, ngày giao dịch, phiên, giờ nghỉ trưa và timeframe.
5. Giữ trạng thái thiếu/không hỗ trợ và provenance.
6. Ngăn look-ahead từ nến tương lai hoặc thông tin audit.
7. Test timestamp UTC/Việt Nam tương đương, ranh giới ngày/phiên, rerun và
   backfill.

Các quy ước này chỉ là tài liệu. Không cần migration, thay đổi dữ liệu hoặc
backfill.

Feature aggregate giữ `stock_intraday.time` làm bucket start theo giờ Việt Nam biểu diễn UTC. Production feature chỉ ghi bucket đã đóng theo biên phiên phù hợp; partial aggregate quan sát được không chứng minh bucket đã đóng.

## Foreign EOD Feature V1

Xem [`docs/FOREIGN_EOD_FEATURES.vi.md`](FOREIGN_EOD_FEATURES.vi.md) về bảng riêng đã duyệt, công thức, calendar/freshness, quyền RPC, CLI và runbook thủ công.

## Preview intraday SSI v3 nhiều trang (chỉ đọc)

Route `stock-intraday`/native `intraday-ohlc` của REST inspector nay dùng adapter preview chung và tải mọi trang từ trang bắt đầu đến kết thúc tường minh hoặc lỗi/giới hạn. `--limit` chỉ giới hạn in; `--full-json` bao gồm mọi trang raw đã nhận và clean candidate. `--max-pages` mặc định 100 (1–1000); chạm giới hạn, trang lặp, total không khớp hay lỗi request trả FAILED/exit 1 và giữ bằng chứng đã nhận. Không đổi các route daily/index/catalog một-trang của inspector.

Mẫu SSI live do chủ sở hữu cung cấp cho 2026-10-20 xác nhận `ohlc.tradingDate` dạng `YYYY/MM/DD HH:mm:ss`, field `ohlc.value` và terminal `{"code":204,"msg":"No Content"}`. Diễn giải tường minh đúng format nguồn này theo `Asia/Ho_Chi_Minh`, rồi chuyển UTC; vẫn hỗ trợ dạng có offset hợp lệ. Alias `time` cũ vẫn bắt buộc timezone. Từ chối chỉ ngày/chỉ giờ và dạng naive khác; không tạo ngày từ request hay dịch phút.

Canonical v3 `value` là **SSI-reported intraday candle value** (giá trị nến intraday SSI trả về), parse chính xác số nguyên không âm trong signed BIGINT, không qua float. **Không ước tính hoặc tính bù**. Nguồn thiếu/null/rỗng giữ NULL kèm SOURCE_VALUE_MISSING; sai định dạng/không hữu hạn/lẻ/âm/tràn bị từ chối. Zero giữ nguyên zero. Report tách nguồn có value, numeric hợp lệ, mapping giữ nguyên và xác minh độc lập ý nghĩa thị trường (vẫn false).

Envelope 204/No Content đã xác nhận chỉ kết thúc paging OHLC 1m khi không có payload/marker lỗi mâu thuẫn và đã qua kiểm tra metadata/số đếm. Giữ nguyên raw envelope, termination provider_no_content_204. Trang ngắn không rỗng không tự kết thúc; trang lặp, total sai, malformed/lỗi và cắt cụt do giới hạn vẫn fail. --limit chỉ giới hạn in; --full-json giữ các trang raw đã nhận, candidate và diagnostic.

Ngày được cung cấp có 226 hàng unique trên 23 trang không rỗng rồi trang 24, thứ tự giảm dần, 135 nến sáng/90 chiều/một nến 14:45. Đây là quan sát do chủ sở hữu báo cho riêng ngày đó, không phải số count hay công thức chung. Chỉ có hai object candle thật và terminal envelope được cung cấp; replay offline xác minh 2/2, không tái tạo các hàng còn thiếu. Agent live rerun: NOT_RUN (thiếu credential). Bar-start/end, ý nghĩa value/turnover độc lập và completeness thị trường còn chưa xác minh. Ingest tự động/schedule vẫn tắt; inspector preview không đọc/ghi DB. Pilot thủ công riêng cần --write tường minh; diagnostic không gọi pilot.

Xem [runbook và checklist](STOCK_INTRADAY_PIPELINE.vi.md) để biết mapping từng field, paging, validation/session/gap, giới hạn nguồn và cách promotion riêng.

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

## Đối soát lineage Phase 0 SSI v3

Reconciliation chỉ SELECT persisted raw/clean/features đúng mã/ngày Việt Nam; không ingest hay tính feature. Chỉ source `ssi_v3` dùng mapper hiện có; `SSI` legacy và TradingDate/Time/Value khác nghĩa không được coi như v3. So timestamp theo instant UTC, giữ giây; --timestamp không lấy hàng lân cận. Volume/value nguyên chính xác không qua float/tolerance, OHLC dùng tolerance tường minh. NULL vẫn NULL, không ước tính từ close*volume hoặc đổi thành zero; aggregate thiếu input báo UNKNOWN trước helper legacy. 1m không cần feature; 15m/60m dùng bucket trái/ngày/phiên/closure của helper hiện có, không yêu cầu số nến cố định. PASS là khớp có evidence, FAIL là mâu thuẫn xác minh được, UNKNOWN là thiếu/ambiguous/unsupported; FAIL không bị UNKNOWN che. Completeness OK chỉ là structural check, không chứng nhận mọi phút thị trường. Không thay schema/dữ liệu/backfill. [Runbook](../scripts/checks/README.vi.md).
