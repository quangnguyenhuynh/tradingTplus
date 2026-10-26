# TradingTPlus CLI — Tham chiếu kỹ thuật đầy đủ

[Hướng dẫn nhanh](CLI_USAGE.vi.md) · [English](CLI_REFERENCE.md)

## Backfill intraday operator có guard

`stock-intraday-backfill` (alias tương thích `backfill-intraday`) nay gọi manual pilot hiện có tuần tự theo range inclusive và symbols tường minh. Mặc định **DRY_RUN**; chỉ `--write` mới persist. `--dry-run`/`--write` loại trừ nhau. Ngày nhận DD/MM/YYYY hoặc YYYY-MM-DD, giữ alias --from-date/--to-date. Không ALL/wildcard/comma scope, universe ngầm, ngày tương lai/range đảo hoặc force overwrite. Normalize/loại trùng symbols giữ thứ tự nhập; ngày tăng dần rồi mã theo thứ tự đó. Chặn quá **50 cặp symbol/weekday** trước service. Cuối tuần không gọi nguồn; range chỉ cuối tuần là OK no-op.

```bash
python main.py stock-intraday-backfill --from 19/10/2026 --to 21/10/2026 --symbols SSI HPG --data-source ssi_v3 --dry-run
# Chỉ owner sau khi đọc dry-run/preflight:
python main.py stock-intraday-backfill --from 19/10/2026 --to 21/10/2026 --symbols SSI HPG --data-source ssi_v3 --write
```

Mỗi cặp tái sử dụng `run_manual_intraday()`: eligibility cả hai status persisted active, paging/map/value SSI v3 toàn ngày, conflict preflight đúng UTC của ngày Việt Nam, chèn raw trước clean không overwrite rồi readback. Không SSI v2, sửa timestamp, ước tính value, lọc bỏ hàng lỗi hoặc ghi đè conflict. Giữ JSON/hash raw và BIGINT `ohlc.value` chính xác; completeness UNVERIFIED, không ép 226 nến. Nguồn rỗng hợp lệ là NO_SOURCE_DATA, không xác nhận holiday hoặc thành công. Ngày lịch sử không hỗ trợ/batch sai được báo rõ. Dry-run không mutation/partition RPC, actual inserts=0 và planned riêng; thiếu DB preflight là BLOCKED, không write-ready.

Conflict/validation lỗi từng cặp được ghi rồi tiếp tục an toàn; lỗi cấu hình/auth/shared dependency đã hết retry thì dừng, giữ completed và unprocessed scope. Không tự retry DB write chưa rõ kết quả. Pair PARTIAL giữ raw đã commit/count được xác nhận và recovery; kiểm tra đúng scope chỉ đọc, xử lý nguyên nhân rồi rerun tường minh. Hàng giống skip, clean thiếu có thể được bổ sung qua guard cũ; không cleanup/delete hoặc hứa atomic xuyên bảng. Range OK khi mọi cặp được xác minh (hoặc không có việc); có verified success lẫn lỗi là PARTIAL; không có cặp success mà có lỗi là FAILED, kể cả đã commit raw dở ở một pair. Pair PARTIAL/count vẫn hiện rõ trong range FAILED. CLI exit 0 chỉ khi OK, 1 cho range lỗi/không xác minh đủ, 2 cho scope/source/argument sai; không đổi exit CLI khác.

JSON range giữ `flow=backfill-intraday`, có planned/processed/OK/blocked/partial/failed/no-source pairs, tổng count, planned insert, halted/unprocessed scope và report pilot trong per_symbol_date. Chỉ giữ summary; batch raw/clean được giải phóng sau mỗi cặp. Registry vẫn preview, không có intraday production factory chung. Stock-intraday một mã/ngày giữ nguyên; intraday-ingest tự động, backfill kết hợp, refill và streaming vẫn tắt; master có luồng guard với dataset SSI v3 BLOCKED. Không tự chạy feature/completeness/signal/backtest/alert. Workflow stock-intraday vẫn tắt, không schedule. Không migration hoặc backfill trong phát triển; Codex không ghi live. Xem [runbook](backfill/README.vi.md) về phục hồi và post-write check chỉ đọc.

Tên CLI canonical và alias tương thích (không có lịch bỏ alias): `stock-daily-backfill` → `backfill-daily`; `stock-intraday-backfill` → `backfill-intraday`; `index-daily-backfill` → `index-backfill`. Giữ tên CLI tương thích; daily/index không đổi. Intraday dùng contract range operator có guard. Stock Daily/Index Daily backfill ACTIVE / WRITE; Stock Intraday backfill có guard, chỉ operator, mặc định DRY_RUN, ghi cần --write và tối đa 50 cặp weekday; luồng tự động vẫn tắt.

[English](CLI_USAGE.md)


## Pilot intraday thủ công có guard

`stock-intraday` hỗ trợ đúng một mã và ngày giao dịch Việt Nam tường minh. Mặc định/`--dry-run` là READ-ONLY; chỉ `--write` mới cho phép chuỗi chèn raw → clean có kiểm soát. Cần credential SSI; credential service Supabase cho phép preflight chỉ đọc eligibility/xung đột và bắt buộc khi ghi. Nếu chưa cấu hình DB, dry-run báo `NOT_RUN_NO_CREDENTIALS`, số dự kiến chưa biết và `write_ready=false`.

```bash
python main.py stock-intraday 20/10/2026 --symbols SSI
python main.py stock-intraday 20/10/2026 --symbols SSI --write
```

Lệnh thứ hai **chỉ dành cho chủ sở hữu sau khi kiểm tra dry-run/preflight**. Không nhận khoảng ngày, ALL/wildcard, scope thiếu, nhiều mã hoặc ngày tương lai. Cả hai status trong master phải active. Chỉ nguồn `ssi_v3`, timeframe `1m`; value canonical giữ chính xác `ohlc.value`, thiếu/sai sẽ chặn pilot và không ước tính bù. Hàng giống giữ nguyên; clean khác giá trị hoặc raw xung đột key/source/payload sẽ chặn. Không force overwrite. Xác nhận raw trước clean; ghi dở dang/không rõ kết quả trả exit khác 0, cần kiểm tra đúng scope rồi chạy lại an toàn. Không cam kết transaction xuyên hai bảng. Completeness vẫn UNVERIFIED. Intraday-ingest tự động, backfill kết hợp, refill, streaming và schedule vẫn tắt. Pilot không chạy feature/signal/backtest.

Xem [runbook](STOCK_INTRADAY_PIPELINE.vi.md) về thứ tự ghi, idempotency, partition, phục hồi và xác minh của chủ sở hữu. Inspector vẫn hoàn toàn chỉ đọc; registry giữ preview, không có factory production chung.

## Giới thiệu và trạng thái chức năng

Đối chiếu commit `b5cb3276` trên `dev` (PR #178). Chạy tại thư mục gốc repository. Ngày và mã trong ví dụ chỉ minh họa; kiểm tra nguồn và chọn đúng phạm vi trước khi chạy. Chỉ kiểm tra cú pháp offline, chưa gọi SSI hay Supabase thật.

Ingest Stock Daily (`securitiesSummary`) và Index Daily (`indexSummary`) qua SSI v3: ACTIVE. Feature stock, foreign và index: ACTIVE trên dữ liệu clean đã lưu. Screener và Historical Analog: RESEARCH_ACTIVE. Master sync có orchestrator guard, dataset SSI v3 BLOCKED; streaming và chụp orderbook vẫn NOT_IMPLEMENTED. Không có fallback về nguồn đã nghỉ.

READ-ONLY — database read: chỉ đọc nhưng vẫn cần kết nối DB. READ-ONLY — SSI API request: có thể gọi API thật nhưng không dùng Supabase. WRITE: có ghi dữ liệu, bao gồm apply và thay thế phạm vi. UNSUPPORTED: đầu vào hoặc thao tác bị từ chối, không phải kết quả rỗng thành công.

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


## Help và quy ước

`--help` chỉ phân tích tham số rồi thoát, không chạy service. Tách mã cổ phiếu bằng khoảng trắng; hệ thống trim, viết hoa, loại trùng. Phạm vi mã rỗng tường minh không hợp lệ. Ingest/check/feature index nhận mã cách nhau bằng khoảng trắng và dùng casing chuẩn từ `index_master`; riêng index-preview nhận một chuỗi phân cách bằng dấu phẩy. Mọi khoảng ngày bên dưới đều bao gồm hai đầu.

Luồng nguồn stock, feature stock, foreign và index nhận `DD/MM/YYYY` hoặc `YYYY-MM-DD`; Analog bắt buộc `DD/MM/YYYY`. Script đối soát Phase 0 bắt buộc ngày ISO. Diễn giải phiên theo `Asia/Ho_Chi_Minh`, giữ timestamp thị trường có timezone. Ngày trong tuần chưa chứng minh có phiên giao dịch.


```bash
python main.py --help
python main.py stock-eod --help
python main.py analogs --help
python scripts/inspectors/ssi_rest/inspect.py run --help
```


## Quy trình bắt đầu nhanh

Bắt đầu bằng preview SSI chỉ đọc. Ingest cần master đã có: đồng bộ master có luồng guard nhưng cả bốn dataset SSI v3 còn BLOCKED nên cài mới không thể tự khởi tạo bằng `init`. Sau khi xác minh summary ingest, tính feature bằng lệnh riêng. Mỗi lệnh dưới đây độc lập; dừng đọc kết quả trước khi tiếp tục.

Preview: READ-ONLY — SSI API request. Stock EOD: WRITE — raw/clean ingest. Daily feature: WRITE — feature calculation. Screener mặc định: READ-ONLY — database read. Không chạy các lệnh ghi chỉ để thử tài liệu.


```bash
python scripts/inspectors/ssi_rest/inspect.py run stock-daily --symbol SSI --date 19/10/2026 --show-mapping
python main.py stock-eod 19/10/2026 --symbols SSI --data-source ssi_v3
python main.py features-daily --date 19/10/2026 --symbols SSI
python main.py stock-screener --date 19/10/2026 --symbols SSI --version v2
```


## Ingest Stock Daily

`daily`: WRITE — raw/clean ingest. Đọc SSI v3 `securitiesSummary`, giữ payload/hash nguồn trong `stock_raw_daily`, validate rồi lưu `stock_daily` chuẩn. Không chạy completeness hay tính toán tầng sau. Bỏ ngày: chọn ngày trong tuần gần nhất trước hôm nay tại Việt Nam. Mã tường minh được dùng trực tiếp; bỏ mã: lấy master active đã lưu.

`stock-eod` và alias chính xác `stock-daily`: WRITE — raw/clean ingest kèm completeness chỉ cho daily. Mã tường minh được giao với master active, báo các mã không biết/inactive bị bỏ. Không có mã active trả FAILED. Ngày mặc định là ngày trong tuần gần nhất tính cả hôm nay tại Việt Nam, khác `daily`. Completeness đối chiếu thời điểm lần chạy và source kỳ vọng. Không ingest index/intraday, không ghi dataset foreign-trading riêng, không tự chạy feature. Trường đếm/summary intraday cũ không có nghĩa là đã ingest intraday.

Ngày ghi nguồn tường minh ở cuối tuần/tương lai bị từ chối. Ngày nghỉ trả rỗng được báo, không tạo hàng giả. Cần cả credential SSI và Supabase.


```bash
python main.py daily --help
python main.py stock-eod --help
python main.py stock-daily --help
python main.py daily 19/10/2026 --symbols SSI
python main.py daily 19/10/2026 --symbols SSI HPG --data-source ssi_v3
python main.py daily --symbols SSI
python main.py stock-eod --symbols SSI
python main.py stock-daily 19/10/2026 --symbols SSI HPG
```


## Backfill lịch sử Stock Daily

WRITE — raw/clean ingest: `stock-daily-backfill` bắt buộc `--from`, `--to`; alias là `--from-date`, `--to-date`. Mã tùy chọn áp dụng cho từng ngày; bỏ mã dùng master active trong mỗi lần ingest. Có thể chỉ định `--data-source ssi_v3`; bỏ tùy chọn chọn adapter v3 ready, không truyền chuỗi `auto`.

Runner bỏ cuối tuần, từ chối khoảng đảo/tương lai, ghi trạng thái OK/PARTIAL/FAILED từng ngày và tiếp tục khi có lỗi. Khoảng chỉ có cuối tuần là OK không làm gì. Không chạy completeness: đọc summary từng ngày và kiểm tra chỉ đọc với phạm vi riêng. Chạy lại có thể cập nhật clean và giữ bằng chứng raw. Không tính feature hay gọi combined backfill đang tắt.


```bash
python main.py stock-daily-backfill --help
python main.py stock-daily-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI HPG --data-source ssi_v3
```


## Preview và ingest Index Daily

`index-preview`: READ-ONLY — SSI API request, không đọc/ghi DB. Bắt buộc `--date` hoặc cặp `--from`, `--to`, cùng `--indexes` là chuỗi mã phân cách dấu phẩy. Mặc định in bảng chuẩn hóa; `--raw` in JSON raw, `--json` in JSON chuẩn hóa; hai cờ loại trừ nhau. Không có tùy chọn production `--data-source` tại đây.

`index-daily`: WRITE — raw/clean ingest từ SSI v3 `indexSummary` vào `index_raw_daily`, sau đó `index_daily` đã validate. Ngày positional tùy chọn mặc định là ngày trong tuần gần nhất tính cả hôm nay tại Việt Nam. `--indexes` nhận một/nhiều mã cách bằng khoảng trắng. Bỏ mã chọn `index_master` active; mã tường minh phải có trong master (có thể chọn hàng inactive). Master rỗng hoặc mã không biết gây ValueError, thường exit CLI 2. Thông báo lỗi gợi ý sync-master-data nhưng dataset SSI v3 của lệnh còn BLOCKED: kiểm tra master đã lưu và xử lý bằng bảo trì được cho phép riêng. Preview không cần master.


```bash
python main.py index-preview --help
python main.py index-daily --help
python main.py index-preview --date 2026-10-19 --indexes VNINDEX --raw
python main.py index-preview --from 2026-10-01 --to 2026-10-19 --indexes VNINDEX,HNXINDEX --json
python main.py index-daily 19/10/2026 --indexes VNINDEX HNXINDEX --data-source ssi_v3
python main.py index-daily 19/10/2026
```


## Backfill và completeness Index Daily

`index-daily-backfill`: WRITE — raw/clean ingest, bắt buộc cặp ngày bao gồm hai đầu `--from`/`--to` (alias `--from-date`/`--to-date`), tùy chọn mã `--indexes` theo master và source. Bỏ cuối tuần, báo số ngày/index; không tự tính feature.

`index-check`: READ-ONLY — database read, kiểm tra raw/clean của ngày positional tùy chọn và mã trong master. Mặc định ngày trong tuần trước hôm nay, khác index-daily. Chỉ cần credential DB. Có raw không chứng minh có clean hợp lệ. Sau ingest OK/PARTIAL vẫn phải đọc bằng chứng validation/completeness.


```bash
python main.py index-daily-backfill --help
python main.py index-check --help
python main.py index-daily-backfill --from 01/10/2026 --to 19/10/2026 --indexes VNINDEX HNXINDEX
python main.py index-check 19/10/2026 --indexes VNINDEX
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


## Feature và xếp hạng foreign EOD

Foreign V2 chỉ dùng các hàng `stock_daily` cùng mã theo trading_date, cửa sổ theo số hàng quan sát; không đọc/suy diễn calendar file. Foreign thiếu vẫn để thiếu. Chỉ ghi `stock_foreign_features_daily`, không sửa nguồn. Sửa lịch sử có thể ảnh hưởng cửa sổ sau; xem ngày bị ảnh hưởng trong report. Xem [đặc tả Foreign EOD](FOREIGN_EOD_FEATURES.vi.md).

Preview (`--symbol`, `--date`, tùy chọn `--show-source`/`--json`) và check (`--from`, `--to`, tùy chọn `--symbols`): READ-ONLY — database read. Daily/backfill: WRITE — feature calculation trừ khi có `--dry-run`, khi đó chỉ tính/validate không persist. Daily bắt buộc ngày, nhận `--mode target|incremental` (mặc định target); backfill bắt buộc hai ngày. Bỏ mã dùng phạm vi active từ DB. `--calendar-file` chỉ là tham số tương thích đã deprecated và bị bỏ qua, không phải điều kiện chạy.

`foreign-rank`, `foreign-symbol`: READ-ONLY — database RPC (`get_foreign_ranking`, `get_foreign_symbol_history`). Rank bắt buộc ngày/ranking; ranking gồm attention, accumulation, distribution, emerging. Window 1/5/20 (mặc định 5), sort value/ratio (value); tùy chọn market, symbols, top (20), offset (0). History bắt buộc một mã/ngày, lookback mặc định 20. RPC/schema phải có sẵn; exit 0 không xác nhận có hàng hoặc dữ liệu mới. Đọc quality, coverage, freshness trước khi diễn giải thứ hạng.


```bash
python main.py foreign-features-preview --symbol SSI --date 19/10/2026 --show-source
python main.py foreign-features-daily --date 19/10/2026 --symbols SSI HPG --dry-run
python main.py foreign-features-daily --date 19/10/2026 --symbols SSI --mode target
python main.py foreign-features-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI --dry-run
python main.py foreign-features-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI
python main.py foreign-features-check --from 01/10/2026 --to 19/10/2026 --symbols SSI
python main.py foreign-rank --date 19/10/2026 --ranking attention --window 1 --symbols SSI HPG --top 20
python main.py foreign-rank --date 19/10/2026 --ranking accumulation --window 5 --sort value --symbols SSI HPG --top 20
python main.py foreign-rank --date 19/10/2026 --ranking distribution --window 20 --sort ratio --top 20
python main.py foreign-rank --date 19/10/2026 --ranking emerging --window 5 --sort value --top 20
python main.py foreign-symbol --symbol SSI --date 19/10/2026 --lookback 20
```


## Feature chỉ số

Domain feature index độc lập đọc `index_daily`, lưu `index_features_daily` theo `(index_code,trading_date)`. Chỉ cần DB, không gọi SSI. Preview/check: READ-ONLY — database read. Daily/backfill: WRITE — feature calculation. Preview/daily bắt buộc `--date`; backfill/check bắt buộc `--from`, `--to` (không có alias dài cho ngày tại đây). `--indexes` tùy chọn nhận mã master cách bằng khoảng trắng; bỏ chọn master active. Dùng tối đa 250 phiên clean trước đó để warm-up. Không tạo OHLC hay phiên thiếu; cửa sổ chưa đủ giữ null. Đọc các ngày raw thiếu clean/thiếu feature trước khi chạy lại phạm vi chính xác.


```bash
python main.py index-features-preview --date 19/10/2026 --indexes VNINDEX
python main.py index-features-daily --date 19/10/2026 --indexes VNINDEX HNXINDEX
python main.py index-features-backfill --from 01/10/2026 --to 19/10/2026 --indexes VNINDEX HNXINDEX
python main.py index-features-check --from 01/10/2026 --to 19/10/2026 --indexes VNINDEX
```


## Stock Screener V1 và V2

`stock-screener` bắt buộc `--date`, tùy chọn mã và `--version v1|v2` (mặc định v1). Mặc định READ-ONLY — database read; đọc master active và `stock_features` 1d đúng ngày. Không tải/tính bù feature thiếu. Đầu vào thiếu không được biến thành kết quả đạt giả. `--apply`: WRITE — explicit apply vào `stock_screener_results`, khóa `(symbol,trading_date,screener_version)`.

`stock-screener-config` preview methodology V2 bất biến tại local, không cần DB; mặc định version v2, language vi (cũng hỗ trợ en). Có `--apply` sẽ đọc/đăng ký `screener_configs`; hash xung đột bị từ chối. Đăng ký config V2 khớp trước khi ghi kết quả V2. Migration screener phải có sẵn; không apply chỉ vì đọc hướng dẫn này. Cả hai là bộ lọc nghiên cứu giải thích được, chưa phải tín hiệu giao dịch đã kiểm chứng. Xem [package Screener](../src/research/screener/README.vi.md) và [methodology V2](../src/research/screener/methodologies/v2.vi.md).


```bash
python main.py stock-screener --help
python main.py stock-screener-config --version v2 --language vi
python main.py stock-screener-config --version v2 --language en
python main.py stock-screener --date 19/10/2026 --symbols SSI HPG --version v1
python main.py stock-screener --date 19/10/2026 --symbols SSI --version v2
python main.py stock-screener-config --version v2 --apply
python main.py stock-screener --date 19/10/2026 --symbols SSI --version v2 --apply
```


## Vòng đời Historical Analog và nghiên cứu

Cây lệnh thực tế gồm `profiles list|register|sync`, `history build`, `validate`, `approve`, `reject`, `query`, `inspect`, `daily run`. Không có subcommand report riêng. Dùng JSON inspect/validate/query làm báo cáo. Ngày tại đây bắt buộc DD/MM/YYYY. Profile bất biến theo code/version/config hash; có nguồn V1 và V2. Xem hash nguồn bằng đăng ký dry-run trước khi đăng ký DB.

Đăng ký profile không apply là dry-run local, không cần credential. Profile list đọc `analog_profiles`. History build đọc clean daily/feature và dựng snapshot/outcome; không apply chỉ đọc DB/tính toán, apply ghi `analog_snapshots`, `analog_outcomes`. Full/incremental theo cơ chế persist hiện có; replace còn cần `--confirm-replace`, có thể xóa đúng phạm vi profile/mã/ngày. Không dùng hash của profile/version khác.

Inspect: READ-ONLY — database read kèm tính nghiên cứu, bắt buộc distance threshold tường minh. Query và daily run là luồng phân tích có gate, mặc định READ-ONLY; khi được phép và có apply là WRITE — explicit apply. Có thể lưu bằng chứng query/match (`analog_queries`, `analog_query_matches`), không tạo tín hiệu giao dịch. Approve/reject cần validation-run ID thật, reviewer và reason; mặc định dry-run, apply có thể ghi review/registry (`analog_profile_reviews`, `analog_profiles`). Ví dụ dưới cố ý dùng dry-run. UUID review minh họa phải thay bằng ID run hợp lệ đã có.

**Điểm BLOCKED trong vòng đời:** parser nhận `validate --apply` nhưng handler không truyền apply, không persist kết quả calibration/walk-forward vào `analog_validation_runs`. Review cần hàng validation đã tồn tại. Vì vậy chỉ CLI chưa hoàn thành vòng đời validation/approval mới; exit 0 không chứng minh validation được lưu. Calibration cần `--final-test-start`; threshold tùy chọn chỉ là ứng viên thử, không phải khuyến nghị production. Query có thể trả `blocked` trước khi tạo DB client nếu source profile chưa được approve. Không có lệnh nào bỏ qua gate approval.

Chỉ so một mã với lịch sử trước đó của chính mã ấy tại cùng checkpoint EOD. Outcome phải quan sát được tại ngày query; validation theo thời gian với baseline cùng mã/checkpoint, không chia ngẫu nhiên hay gộp mã. `insufficient_sample` là kết quả hợp lệ, không được tự mở rộng universe. Xem [đặc tả Historical Analog](phase1/HISTORICAL_ANALOG_SPEC.vi.md) để biết hợp đồng bằng chứng.


```bash
python main.py analogs profiles list
python main.py analogs profiles register --profile TPLUS_ANALOG_CORE_EOD --version 1
python main.py analogs profiles sync --profile TPLUS_ANALOG_CORE_EOD --version 1
python main.py analogs history build --profile TPLUS_ANALOG_CORE_EOD --version 1 --config-hash d19417afed8718337c12aae7a668dd68e0f323dbb9c2316c92a5122759e9751b --symbols SSI --from 05/01/2026 --to 19/10/2026 --mode incremental
python main.py analogs validate --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbols SSI --from 05/01/2026 --to 30/09/2026 --run-type calibration --final-test-start 01/10/2026 --thresholds 0.5 1.0
python main.py analogs validate --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbols SSI --from 01/10/2026 --to 19/10/2026 --run-type validation
python main.py analogs validate --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbols SSI --from 01/10/2026 --to 19/10/2026 --run-type final
python main.py analogs inspect --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbol SSI --date 19/10/2026 --checkpoint EOD --distance-threshold 1.0
python main.py analogs query --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbol SSI --date 19/10/2026
python main.py analogs daily run --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbols SSI --date 19/10/2026
python main.py analogs approve --profile TPLUS_ANALOG_CORE_EOD --version 1 --validation-run 00000000-0000-0000-0000-000000000001 --reviewer operator --reason "Review existing final evidence"
python main.py analogs reject --profile TPLUS_ANALOG_CORE_EOD --version 1 --validation-run 00000000-0000-0000-0000-000000000001 --reviewer operator --reason "Evidence incomplete"
```


## SSI v3 REST inspector

READ-ONLY — SSI API request; không truy cập Supabase kể cả preview master/intraday. `list` không cần credential hay mạng. `run` cần key/secret SSI v3, gọi dữ liệu thật và map local các dataset được hỗ trợ. Preview có sẵn không chứng minh ingest production đã sẵn sàng. Xem [runbook inspector đầy đủ](../scripts/inspectors/ssi_rest/README.vi.md) cho endpoint native, alias tương thích, paging, raw/clean mapping, ngày, giới hạn, lỗi.


```bash
python scripts/inspectors/ssi_rest/inspect.py --help
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 19/10/2026 --limit 5 --show-mapping
```


## Công cụ chất lượng và completeness

Phase 0 hỗ trợ `1m`, `1d`, `15m`, `60m`; 1m không cần feature. Schema check dùng stock_raw_intraday/stock_features canonical và giữ RPC security. Chỉ source ssi_v3 được map lại; legacy/thiếu/ambiguous UNKNOWN, mismatch thật FAIL. Volume/value nguyên chính xác, OHLC tolerance 1e-6; timestamp aware đúng instant, không làm tròn giây. Aggregate chỉ so OHLCV/value observed bucket đã đóng bằng helper hiện có, NULL/dở/thiếu evidence UNKNOWN; không tính feature. Reconciliation exit 0 PASS/WARNING, 1 FAIL, 2 UNKNOWN, payload-presence chỉ là thông tin. Mọi diagnostic chỉ đọc.

Các check active dưới đây đều READ-ONLY — database read. `check_ingest.py` kiểm tra coverage stock daily/intraday đã lưu; trả exit 0 khi OK, 1 khi PARTIAL/FAILED hoặc lỗi query, 2 khi input sai/kết quả không xác định. Giữ status gốc trong JSON stdout, progress đưa sang stderr. Coverage intraday được kiểm tra độc lập pilot thủ công. `check_supabase.py` không có tham số CLI/help parser: kiểm tra kết nối bảng lõi, không chứng nhận toàn bộ schema. `check_ssi_ingest_schema.py` select danh sách cột và in SQL kiểm tra index; kỳ vọng cột cũ có thể lệch contract 2.0, cần sửa code riêng, không đổi schema chỉ để chiều diagnostic.

`phase0_validate_schema.py` query catalog PostgreSQL chỉ đọc; ưu tiên biến môi trường thay vì ghi URL DB vào shell history. `phase0_reconcile_sample.py` kiểm tra một mã/ngày/timeframe, tùy chọn timestamp chính xác và tolerance 1e-6. PASS/FAIL/UNKNOWN có ý nghĩa riêng với việc tiến trình chạy được. Xem [công cụ kiểm tra](../scripts/checks/README.vi.md).


```bash
python scripts/checks/check_ingest.py --date 19/10/2026 --symbols SSI
python scripts/checks/check_supabase.py
python scripts/checks/check_ssi_ingest_schema.py
python scripts/checks/phase0_validate_schema.py
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-19 --timeframe 1d
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 1m
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 15m
```


## Script chẩn đoán, bảo trì và debug

[Danh mục script](../scripts/README.vi.md) liệt kê mọi công cụ thực thi theo đường dẫn hiện tại. **`scripts/previews/run_features.py` là WRITE — feature calculation** dù nằm trong previews. Nó gọi engine, không có cờ dry-run/ngày và có thể xử lý lịch sử theo mode/watermark. Ưu tiên route feature main.py có ngày đích tường minh. Tên/vị trí script là vấn đề code riêng; task này không di chuyển.

`eod_dry_run.py`, `fetch_one_day.py`, capture, streaming inspector và complete SSI smoke check là stub đang tắt, không phải pipeline debug chạy được. SQL intraday-value cũ là artifact WRITE rộng không giới hạn mã/ngày, không phải CLI vận hành thường lệ; không dán vào production. Cần review riêng một sửa chữa có phạm vi.


```bash
python scripts/previews/run_features.py --mode incremental --symbols SSI --timeframes 1d
```


## Các lệnh tạm tắt

Các nhóm lệnh còn tắt dưới giữ parser nhưng dừng trước khi nạp handler hoặc tạo client SSI/DB. Trả exit 1 và JSON status FAILED, error_type NOT_IMPLEMENTED. Source tường minh bị từ chối có thể trả exit 2 ở preflight trước đó. Help vẫn mô tả mục đích cũ, không chứng minh khả năng chạy.

| Lệnh | Mục đích trước đây | Adapter / dataset cần trong tương lai |
| --- | --- | --- |
| intraday-ingest | Ingest raw/clean nguồn 1m | Adapter v3 1m, pagination, timestamp, đơn vị đã xác minh; stock_intraday |
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


## Exit code, kết quả kỳ vọng và xử lý lỗi

Exit CLI 0 bao gồm OK, PARTIAL ở luồng hỗ trợ và các trạng thái domain như Analog blocked/dry_run/insufficient_sample. Exit 1: FAILED, capability chưa có hoặc exception runtime. Exit 2: lỗi argparse/ValueError hoặc source không hỗ trợ. Phần lớn handler chỉ kiểm tra `status == FAILED`; lệnh RPC foreign và index-preview trả 0 khi hàm hoàn tất bất kể completeness. Parse được, API thành công, persist thành công và completeness đạt là bốn bước khác nhau.

JSON minh họa, không phải kết quả đã chạy thật:

```json
{"date":"19/10/2026","data_source":"ssi_v3","symbols":["SSI"],"daily_valid_count":1,"total_daily_rows":1,"error_count":0,"errors":[],"status":"OK"}
```

```json
{"status":"FAILED","error_type":"NOT_IMPLEMENTED","dataset":"stock_intraday","reason":"SSI v3 stock_intraday ingestion adapter is not implemented"}
```

| Hiện tượng | Cách xử lý |
| --- | --- |
| ImportError / thiếu create_client | Kích hoạt venv đã cài và cài requirements; thư mục supabase local không phải Python SDK. |
| Source sai / option không biết | Chỉ dùng ssi_v3 nơi parser có source; tự chọn nguồn nghĩa là bỏ option. |
| Thiếu SSI credential / 401 / 403 | Kiểm tra key/secret v3, quyền tài khoản tại local; không in token hay dùng consumer credential cũ. |
| NO_DATA / EMPTY_RESPONSE | Kiểm tra mã/ngày chính xác, độ trễ công bố và phiên; không tạo hàng giả hoặc coi weekday là phiên. |
| MISMATCH / lỗi mapping | Xem raw payload, identity và diagnostic mapping; không sửa bằng chứng nguồn để ép thành công. |
| Master rỗng | Kiểm tra symbols/index_master đã lưu; dataset master SSI v3 BLOCKED do chưa xác minh nguồn. |
| Có raw, thiếu clean/feature | Xem lỗi validation và warm-up; chỉ chạy feature riêng sau khi kiểm tra nguồn. |
| Lỗi RPC/cột/unique constraint | Đối chiếu schema triển khai với migration hiện có; checkout code không triển khai DB. |
| PARTIAL hoặc exit 0 không có output | Đọc warning, số đếm, phạm vi, kết quả từng ngày; xác minh hàng persist/completeness độc lập. |
| Intraday thiếu | Đối chiếu timestamp/quy tắc phiên của đúng mã/ngày; không dùng số nến cố định cho mọi phiên. |
| Analog blocked / insufficient_sample | Kiểm tra version/hash, lịch sử quan sát được và bằng chứng approval; không gộp mã. |

PASS, EMPTY, FAILED của REST inspector là trạng thái request/mapping, không chứng minh production DB đã sẵn sàng.

## Tác động DB và an toàn vận hành

Thay đổi này chỉ là tài liệu: migration none, tác động DB none, backfill bắt buộc none. Ví dụ WRITE có thể thay dữ liệu nếu chủ động chạy sau này; không được thực thi để validate tài liệu.

| Thao tác | Bảng đích / tác động |
| --- | --- |
| Nguồn stock | stock_raw_daily giữ bằng chứng nguồn; stock_daily clean đã validate |
| Nguồn index | index_raw_daily bằng chứng; index_daily clean |
| Feature stock | Upsert stock_features; scoped replace xóa/ghi lại đúng mã/timeframe/ngày |
| Feature foreign | Upsert stock_foreign_features_daily |
| Feature index | Upsert index_features_daily |
| Apply screener | stock_screener_results; apply config đăng ký screener_configs |
| Apply Analog | Chỉ bảng domain profile/history/query/review, có gate; persist validation bị chặn như đã nêu |
| Inspector/check/dry-run | Không ghi dữ liệu; có thể đọc dịch vụ thật |

Raw và clean tách riêng. Identity raw stock gồm mã/ngày/source/hash, clean stock mã/ngày; raw index gồm index/ngày/hash, clean index index/ngày. Xác nhận constraint đã triển khai trước khi ghi. Chạy lại không phải rollback; có provenance raw cũ không cho phép ghi đè lịch sử rộng. Sau mỗi thao tác đọc phạm vi, số đếm, lỗi, null, source, timestamp. Không suy completeness production từ test offline.

Workflow Stock EOD chạy 16:30 Việt Nam ngày thường; Index EOD chạy 08:30 Việt Nam thứ Ba–thứ Bảy, lịch tự động chọn ngày trước đó theo thời điểm công bố. Default CLI thủ công khác; chỉ định ngày khi tái hiện scheduled run. Intraday không có ingest theo lịch. Workflow feature chạy tường minh. Xem [quy ước dữ liệu](DATA_CONVENTIONS.vi.md), [trạng thái](CURRENT_STATE.md), [báo cáo khôi phục](CLI_DOCUMENTATION_AUDIT.vi.md).

## Danh mục đầy đủ và tham số CLI

Mỗi bảng dưới lấy từ parser hiện tại. `+`: ít nhất một giá trị; `*`: không/nhiều giá trị khi parse (phạm vi mã rỗng vẫn bị validation từ chối); `?`: tùy chọn. Mọi lệnh có `-h`, `--help`. Quy tắc ngày/phạm vi, output/lỗi theo từng domain ở trên; exit theo mục xử lý lỗi.

### `sync-master-data` / `init`

Master sync có guard, mặc định DRY_RUN. Dataset SSI v3 hiện **BLOCKED**.
Chỉ OK trả exit 0. [Audit nguồn và runbook](../src/ingest/master/README.vi.md).

| Tham số | Bắt buộc | Mặc định | Giá trị |
| --- | --- | --- | --- |
| --dataset | một dataset tường minh khi ghi | preview tất cả | symbols, securities, index_master, index_components, all (chỉ preview) |
| --data-source | không | READY đã xác minh mới nhất theo dataset; hiện chưa có | ssi_v3 BLOCKED; không đoán v4/v5 |
| --dry-run / --write | loại trừ nhau | DRY_RUN | ghi cần dataset tường minh và capability READY |

### `daily`

Lấy daily cổ phiếu; alias EOD còn kiểm tra completeness.

**WRITE — raw/clean ingest** · Trạng thái: ACTIVE.

Đầu vào: SSI v3 securitiesSummary. Đầu ra/đích: stock_raw_daily → stock_daily.

Credential: SSI có; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `date` | không | `—` | ? |
| `--data-source` | không | `—` | 1 |
| `--symbols` | không | `—` | + |

### `index-daily`

Lấy dữ liệu nguồn daily chỉ số.

**WRITE — raw/clean ingest** · Trạng thái: ACTIVE.

Đầu vào: SSI v3 indexSummary. Đầu ra/đích: index_raw_daily → index_daily.

Credential: SSI có; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `date` | không | `—` | ? |
| `--indexes` | không | `—` | + |
| `--data-source` | không | `—` | 1 |

### `index-daily-backfill`

Alias legacy tương thích: `index-backfill`.

Lấy dữ liệu nguồn daily chỉ số.

**WRITE — raw/clean ingest** · Trạng thái: ACTIVE.

Đầu vào: SSI v3 indexSummary. Đầu ra/đích: index_raw_daily → index_daily.

Credential: SSI có; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--from`, `--from-date` | có | `—` | 1 |
| `--to`, `--to-date` | có | `—` | 1 |
| `--indexes` | không | `—` | + |
| `--data-source` | không | `—` | 1 |

### `index-check`

Kiểm tra completeness chỉ số.

**READ-ONLY — database read** · Trạng thái: ACTIVE.

Đầu vào: index_raw_daily + index_daily. Đầu ra/đích: JSON.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `date` | không | `—` | ? |
| `--indexes` | không | `—` | + |

### `index-preview`

Xem nguồn index raw hoặc chuẩn hóa.

**READ-ONLY — SSI API request** · Trạng thái: ACTIVE.

Đầu vào: SSI v3 indexSummary. Đầu ra/đích: terminal / JSON.

Credential: SSI có; Supabase không. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--date` | không | `—` | 1 |
| `--from` | không | `—` | 1 |
| `--to` | không | `—` | 1 |
| `--indexes` | có | `—` | 1 |
| `--raw` | không | `false` | flag |
| `--json` | không | `false` | flag |

### `index-features-preview`

Xem tính toán/coverage feature index.

**READ-ONLY — database read** · Trạng thái: ACTIVE.

Đầu vào: index_daily + index_features_daily. Đầu ra/đích: JSON.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--date` | có | `—` | 1 |
| `--indexes` | không | `—` | + |

### `index-features-daily`

Tính feature index.

**WRITE — feature calculation** · Trạng thái: ACTIVE.

Đầu vào: index_daily. Đầu ra/đích: index_features_daily.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--date` | có | `—` | 1 |
| `--indexes` | không | `—` | + |

### `index-features-backfill`

Tính feature index.

**WRITE — feature calculation** · Trạng thái: ACTIVE.

Đầu vào: index_daily. Đầu ra/đích: index_features_daily.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--from` | có | `—` | 1 |
| `--to` | có | `—` | 1 |
| `--indexes` | không | `—` | + |

### `index-features-check`

Xem tính toán/coverage feature index.

**READ-ONLY — database read** · Trạng thái: ACTIVE.

Đầu vào: index_daily + index_features_daily. Đầu ra/đích: JSON.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--from` | có | `—` | 1 |
| `--to` | có | `—` | 1 |
| `--indexes` | không | `—` | + |

### `foreign-features-preview`

Xem tính toán/chất lượng foreign.

**READ-ONLY — database read** · Trạng thái: ACTIVE.

Đầu vào: stock_daily + stock_foreign_features_daily. Đầu ra/đích: JSON.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--symbol` | có | `—` | 1 |
| `--date` | có | `—` | 1 |
| `--calendar-file` | không | `—` | 1 |
| `--json` | không | `false` | flag |
| `--show-source` | không | `false` | flag |

### `foreign-features-daily`

Tính feature foreign; dry-run không ghi.

**WRITE — feature calculation / --dry-run READ-ONLY** · Trạng thái: ACTIVE.

Đầu vào: stock_daily. Đầu ra/đích: stock_foreign_features_daily.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--date` | có | `—` | 1 |
| `--symbols` | không | `—` | + |
| `--mode` | không | `"target"` | target, incremental |
| `--calendar-file` | không | `—` | 1 |
| `--dry-run` | không | `false` | flag |

### `foreign-features-backfill`

Tính feature foreign; dry-run không ghi.

**WRITE — feature calculation / --dry-run READ-ONLY** · Trạng thái: ACTIVE.

Đầu vào: stock_daily. Đầu ra/đích: stock_foreign_features_daily.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--from` | có | `—` | 1 |
| `--to` | có | `—` | 1 |
| `--symbols` | không | `—` | + |
| `--calendar-file` | không | `—` | 1 |
| `--dry-run` | không | `false` | flag |

### `foreign-features-check`

Xem tính toán/chất lượng foreign.

**READ-ONLY — database read** · Trạng thái: ACTIVE.

Đầu vào: stock_daily + stock_foreign_features_daily. Đầu ra/đích: JSON.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--from` | có | `—` | 1 |
| `--to` | có | `—` | 1 |
| `--symbols` | không | `—` | + |
| `--calendar-file` | không | `—` | 1 |

### `foreign-rank`

Xếp hạng attention/tích lũy/phân phối/mới nổi.

**READ-ONLY — database read** · Trạng thái: ACTIVE.

Đầu vào: get_foreign_ranking RPC. Đầu ra/đích: JSON.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--date` | có | `—` | 1 |
| `--ranking` | có | `—` | attention, accumulation, distribution, emerging |
| `--window` | không | `5` | 1, 5, 20 |
| `--sort` | không | `"value"` | value, ratio |
| `--market` | không | `—` | 1 |
| `--symbols` | không | `—` | + |
| `--top` | không | `20` | 1 |
| `--offset` | không | `0` | 1 |

### `foreign-symbol`

Đọc lịch sử foreign một mã.

**READ-ONLY — database read** · Trạng thái: ACTIVE.

Đầu vào: get_foreign_symbol_history RPC. Đầu ra/đích: JSON.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--symbol` | có | `—` | 1 |
| `--date` | có | `—` | 1 |
| `--lookback` | không | `20` | 1 |

### `intraday-ingest`

Điều phối nguồn trước đây; hiện chưa triển khai.

**NOT_IMPLEMENTED** · Trạng thái: NOT_IMPLEMENTED.

Đầu vào: none / không gọi dịch vụ. Đầu ra/đích: stock_intraday.

Credential: SSI không; Supabase không. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `date` | không | `—` | ? |
| `--symbols` | không | `—` | + |
| `--data-source` | không | `—` | 1 |

### `stock-eod`

Lấy daily cổ phiếu; alias EOD còn kiểm tra completeness.

**WRITE — raw/clean ingest** · Trạng thái: ACTIVE.

Đầu vào: SSI v3 securitiesSummary. Đầu ra/đích: stock_raw_daily → stock_daily.

Credential: SSI có; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `date` | không | `—` | ? |
| `--symbols` | không | `—` | + |
| `--data-source` | không | `—` | 1 |

### `stock-daily`

Lấy daily cổ phiếu; alias EOD còn kiểm tra completeness.

**WRITE — raw/clean ingest** · Trạng thái: ACTIVE.

Đầu vào: SSI v3 securitiesSummary. Đầu ra/đích: stock_raw_daily → stock_daily.

Credential: SSI có; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `date` | không | `—` | ? |
| `--symbols` | không | `—` | + |
| `--data-source` | không | `—` | 1 |

### `stock-intraday`

**READ-ONLY mặc định / WRITE khi có `--write`** · Trạng thái: MANUAL_PILOT.

SSI v3 OHLC 1m → stock_raw_intraday → stock_intraday; không chạy lớp downstream. Cần SSI, Supabase tùy chọn cho dry-run preflight và bắt buộc khi ghi. Xem pilot/runbook phía trên.

| Tham số | Bắt buộc | Mặc định | Giá trị |
| --- | --- | --- | --- |
| `date` | có (guard) | không | Một DD/MM/YYYY hoặc YYYY-MM-DD, không tương lai |
| `--symbols` | có (guard) | không | Đúng một mã, hai status active |
| `--data-source` | không | ssi_v3 | Chỉ ssi_v3, dataset stock_intraday |
| `--write` | không | false | Cho phép ghi pilot |
| `--dry-run` | không | read-only | Không kết hợp --write |

BLOCKED/PARTIAL/FAILED đều exit 1; scope sai exit 2. Dry-run không tạo partition, số chèn thực luôn 0; planned là trường riêng.

### `stock-daily-backfill`

Alias legacy tương thích: `backfill-daily`.

Lấy lịch sử daily không kèm completeness.

**WRITE — raw/clean ingest** · Trạng thái: ACTIVE.

Đầu vào: SSI v3 securitiesSummary. Đầu ra/đích: stock_raw_daily → stock_daily.

Credential: SSI có; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--from`, `--from-date` | có | `—` | 1 |
| `--to`, `--to-date` | có | `—` | 1 |
| `--symbols` | không | `—` | + |
| `--data-source` | không | `—` | 1 |

### `stock-intraday-backfill`

Alias legacy `backfill-intraday`. **GUARDED_OPERATOR / DRY_RUN mặc định**, --write mới ghi raw/clean. Cần explicit symbols, tối đa 50 cặp weekday, đúng SSI v3/1m. Không feature/completeness tự động. Exit 0 OK, 1 mọi range không thành công, 2 input sai; xem runbook phía trên.

| Tham số | Bắt buộc | Mặc định | Giá trị |
| --- | --- | --- | --- |
| `--from`, `--from-date` | có | không | DD/MM/YYYY hoặc YYYY-MM-DD, inclusive |
| `--to`, `--to-date` | có | không | Ngày inclusive không tương lai/đảo range |
| `--symbols` | có | không | Mã tường minh normalize/dedupe, không ALL/wildcard/comma |
| `--data-source` | không | ssi_v3 | Chỉ ssi_v3 |
| `--dry-run` | không | chỉ đọc | Không kết hợp --write |
| `--write` | không | false | Cho phép ghi từng cặp qua guard pilot |

### `backfill`

Điều phối nguồn trước đây; hiện chưa triển khai.

**NOT_IMPLEMENTED** · Trạng thái: NOT_IMPLEMENTED.

Đầu vào: none / không gọi dịch vụ. Đầu ra/đích: stock_intraday.

Credential: SSI không; Supabase không. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--from`, `--from-date` | có | `—` | 1 |
| `--to`, `--to-date` | có | `—` | 1 |
| `--symbols` | không | `—` | + |
| `--data-source` | không | `—` | 1 |

### `refill`

Điều phối nguồn trước đây; hiện chưa triển khai.

**NOT_IMPLEMENTED** · Trạng thái: NOT_IMPLEMENTED.

Đầu vào: none / không gọi dịch vụ. Đầu ra/đích: stock_intraday.

Credential: SSI không; Supabase không. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--symbol` | có | `—` | 1 |
| `--from`, `--from-date` | có | `—` | 1 |
| `--to`, `--to-date` | có | `—` | 1 |
| `--data-source` | không | `—` | 1 |

### `features`

Tính feature kỹ thuật stock độc lập.

**WRITE — feature calculation** · Trạng thái: ACTIVE.

Đầu vào: stock_daily / clean stock_intraday 1m. Đầu ra/đích: stock_features.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--mode` | không | `"incremental"` | incremental, full |
| `--date` | không | `—` | 1 |
| `--symbols` | không | `—` | * |
| `--timeframes` | không | `["15m", "60m", "1d"]` | * |

### `features-daily`

Tính feature kỹ thuật stock độc lập.

**WRITE — feature calculation** · Trạng thái: ACTIVE.

Đầu vào: stock_daily / clean stock_intraday 1m. Đầu ra/đích: stock_features.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--mode` | không | `"incremental"` | incremental, full, replace, rebuild-clean |
| `--date` | không | `—` | 1 |
| `--from`, `--from-date` | không | `—` | 1 |
| `--to`, `--to-date` | không | `—` | 1 |
| `--symbols` | không | `—` | * |

### `features-intraday`

Tính feature kỹ thuật stock độc lập.

**WRITE — feature calculation** · Trạng thái: ACTIVE.

Đầu vào: stock_daily / clean stock_intraday 1m. Đầu ra/đích: stock_features.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--mode` | không | `"incremental"` | incremental, full, replace, rebuild-clean |
| `--date` | không | `—` | 1 |
| `--from`, `--from-date` | không | `—` | 1 |
| `--to`, `--to-date` | không | `—` | 1 |
| `--symbols` | không | `—` | * |
| `--timeframes` | không | `["15m", "60m"]` | * |
| `--as-of` | không | `—` | 1 |

### `stock-screener`

Đánh giá mã active theo V1/V2; chỉ ghi khi apply.

**READ-ONLY / --apply WRITE** · Trạng thái: RESEARCH_ACTIVE.

Đầu vào: symbols + stock_features 1d. Đầu ra/đích: JSON / stock_screener_results.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--date` | có | `—` | 1 |
| `--symbols` | không | `—` | + |
| `--apply` | không | `false` | flag |
| `--version` | không | `"v1"` | v1, v2 |

### `stock-screener-config`

Xem/đăng ký config V2 bất biến.

**LOCAL / --apply WRITE** · Trạng thái: RESEARCH_ACTIVE.

Đầu vào: local V2 config + methodologies. Đầu ra/đích: JSON / screener_configs.

Credential: SSI không; Supabase không. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--version` | không | `"v2"` | v2 |
| `--language` | không | `"vi"` | vi, en |
| `--apply` | không | `false` | flag |

### `streaming-ingest`

Điều phối nguồn trước đây; hiện chưa triển khai.

**NOT_IMPLEMENTED** · Trạng thái: NOT_IMPLEMENTED.

Đầu vào: none / không gọi dịch vụ. Đầu ra/đích: streaming.

Credential: SSI không; Supabase không. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--symbols` | không | `[]` | * |
| `--indexes` | không | `[]` | * |
| `--channels` | có | `—` | securities-status, quote, trade, foreign-room, index, realtime-bar |
| `--timeout` | không | `60` | 1 |
| `--max-messages-per-channel` | không | `1` | 1 |
| `--write` | không | `false` | flag |
| `--debug` | không | `false` | flag |

### `analogs`

Nghiên cứu EOD cùng mã; vòng đời tường minh.

**READ-ONLY / --apply WRITE (gated)** · Trạng thái: RESEARCH_ACTIVE.

Đầu vào: stock_daily + stock_features + analog_*. Đầu ra/đích: JSON / analog_*.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |

### `analogs profiles`

Nghiên cứu EOD cùng mã; vòng đời tường minh.

**READ-ONLY / --apply WRITE (gated)** · Trạng thái: RESEARCH_ACTIVE.

Đầu vào: stock_daily + stock_features + analog_*. Đầu ra/đích: JSON / analog_*.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |

### `analogs profiles list`

Nghiên cứu EOD cùng mã; vòng đời tường minh.

**READ-ONLY / --apply WRITE (gated)** · Trạng thái: RESEARCH_ACTIVE.

Đầu vào: stock_daily + stock_features + analog_*. Đầu ra/đích: JSON / analog_*.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |

### `analogs profiles register`

Nghiên cứu EOD cùng mã; vòng đời tường minh.

**READ-ONLY / --apply WRITE (gated)** · Trạng thái: RESEARCH_ACTIVE.

Đầu vào: stock_daily + stock_features + analog_*. Đầu ra/đích: JSON / analog_*.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--profile` | không | `"TPLUS_ANALOG_CORE_EOD"` | 1 |
| `--version` | không | `1` | 1 |
| `--config-hash` | không | `—` | 1 |
| `--apply` | không | `false` | flag |

### `analogs history`

Nghiên cứu EOD cùng mã; vòng đời tường minh.

**READ-ONLY / --apply WRITE (gated)** · Trạng thái: RESEARCH_ACTIVE.

Đầu vào: stock_daily + stock_features + analog_*. Đầu ra/đích: JSON / analog_*.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |

### `analogs history build`

Nghiên cứu EOD cùng mã; vòng đời tường minh.

**READ-ONLY / --apply WRITE (gated)** · Trạng thái: RESEARCH_ACTIVE.

Đầu vào: stock_daily + stock_features + analog_*. Đầu ra/đích: JSON / analog_*.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--profile` | có | `—` | 1 |
| `--version` | có | `—` | 1 |
| `--config-hash` | có | `—` | 1 |
| `--symbols` | có | `—` | + |
| `--from` | có | `—` | 1 |
| `--to` | có | `—` | 1 |
| `--mode` | có | `—` | full, incremental, replace |
| `--apply` | không | `false` | flag |
| `--confirm-replace` | không | `false` | flag |

### `analogs validate`

Nghiên cứu EOD cùng mã; vòng đời tường minh.

**READ-ONLY / --apply WRITE (gated)** · Trạng thái: RESEARCH_ACTIVE.

Đầu vào: stock_daily + stock_features + analog_*. Đầu ra/đích: JSON / analog_*.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--profile` | có | `—` | 1 |
| `--version` | có | `—` | 1 |
| `--symbols` | có | `—` | + |
| `--from` | có | `—` | 1 |
| `--to` | có | `—` | 1 |
| `--run-type` | có | `—` | calibration, validation, final |
| `--thresholds` | không | `—` | * |
| `--final-test-start` | không | `—` | 1 |
| `--apply` | không | `false` | flag |

### `analogs approve`

Nghiên cứu EOD cùng mã; vòng đời tường minh.

**READ-ONLY / --apply WRITE (gated)** · Trạng thái: RESEARCH_ACTIVE.

Đầu vào: stock_daily + stock_features + analog_*. Đầu ra/đích: JSON / analog_*.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--profile` | có | `—` | 1 |
| `--version` | có | `—` | 1 |
| `--validation-run` | có | `—` | 1 |
| `--reviewer` | có | `—` | 1 |
| `--reason` | có | `—` | 1 |
| `--apply` | không | `false` | flag |

### `analogs reject`

Nghiên cứu EOD cùng mã; vòng đời tường minh.

**READ-ONLY / --apply WRITE (gated)** · Trạng thái: RESEARCH_ACTIVE.

Đầu vào: stock_daily + stock_features + analog_*. Đầu ra/đích: JSON / analog_*.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--profile` | có | `—` | 1 |
| `--version` | có | `—` | 1 |
| `--validation-run` | có | `—` | 1 |
| `--reviewer` | có | `—` | 1 |
| `--reason` | có | `—` | 1 |
| `--apply` | không | `false` | flag |

### `analogs query`

Nghiên cứu EOD cùng mã; vòng đời tường minh.

**READ-ONLY / --apply WRITE (gated)** · Trạng thái: RESEARCH_ACTIVE.

Đầu vào: stock_daily + stock_features + analog_*. Đầu ra/đích: JSON / analog_*.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--profile` | có | `—` | 1 |
| `--version` | có | `—` | 1 |
| `--symbol` | có | `—` | 1 |
| `--date` | có | `—` | 1 |
| `--checkpoint` | không | `"EOD"` | EOD |
| `--apply` | không | `false` | flag |

### `analogs inspect`

Nghiên cứu EOD cùng mã; vòng đời tường minh.

**READ-ONLY / --apply WRITE (gated)** · Trạng thái: RESEARCH_ACTIVE.

Đầu vào: stock_daily + stock_features + analog_*. Đầu ra/đích: JSON / analog_*.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--profile` | có | `—` | 1 |
| `--version` | có | `—` | 1 |
| `--symbol` | có | `—` | 1 |
| `--date` | có | `—` | 1 |
| `--checkpoint` | không | `"EOD"` | EOD |
| `--distance-threshold` | có | `—` | 1 |

### `analogs daily`

Nghiên cứu EOD cùng mã; vòng đời tường minh.

**READ-ONLY / --apply WRITE (gated)** · Trạng thái: RESEARCH_ACTIVE.

Đầu vào: stock_daily + stock_features + analog_*. Đầu ra/đích: JSON / analog_*.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |

### `analogs daily run`

Nghiên cứu EOD cùng mã; vòng đời tường minh.

**READ-ONLY / --apply WRITE (gated)** · Trạng thái: RESEARCH_ACTIVE.

Đầu vào: stock_daily + stock_features + analog_*. Đầu ra/đích: JSON / analog_*.

Credential: SSI không; Supabase có. Ngoại lệ dry-run local/config preview và gate Analog nêu ở trên.

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `--profile` | có | `—` | 1 |
| `--version` | có | `—` | 1 |
| `--symbols` | có | `—` | + |
| `--date` | có | `—` | 1 |
| `--apply` | không | `false` | flag |

### Đăng ký profile có ghi — chỉ sau khi duyệt dry-run

Đây là WRITE — explicit apply vào analog_profiles, cần DB; không phải lệnh kiểm tra tài liệu.

```bash
python main.py analogs profiles register --profile TPLUS_ANALOG_CORE_EOD --version 1 --apply
```

Nếu chưa có .env local, sao chép mẫu mà không ghi đè cấu hình hiện có:

```bash
cp -n .env.example .env
```

## Preview intraday SSI v3 nhiều trang (chỉ đọc)

Route `stock-intraday`/native `intraday-ohlc` của REST inspector nay dùng adapter preview chung và tải mọi trang từ trang bắt đầu đến kết thúc tường minh hoặc lỗi/giới hạn. `--limit` chỉ giới hạn in; `--full-json` bao gồm mọi trang raw đã nhận và clean candidate. `--max-pages` mặc định 100 (1–1000); chạm giới hạn, trang lặp, total không khớp hay lỗi request trả FAILED/exit 1 và giữ bằng chứng đã nhận. Không đổi các route daily/index/catalog một-trang của inspector.

Mẫu SSI live do chủ sở hữu cung cấp cho 2026-10-20 xác nhận `ohlc.tradingDate` dạng `YYYY/MM/DD HH:mm:ss`, field `ohlc.value` và terminal `{"code":204,"msg":"No Content"}`. Diễn giải tường minh đúng format nguồn này theo `Asia/Ho_Chi_Minh`, rồi chuyển UTC; vẫn hỗ trợ dạng có offset hợp lệ. Alias `time` cũ vẫn bắt buộc timezone. Từ chối chỉ ngày/chỉ giờ và dạng naive khác; không tạo ngày từ request hay dịch phút.

Canonical v3 `value` là **SSI-reported intraday candle value** (giá trị nến intraday SSI trả về), parse chính xác số nguyên không âm trong signed BIGINT, không qua float. **Không ước tính hoặc tính bù**. Nguồn thiếu/null/rỗng giữ NULL kèm SOURCE_VALUE_MISSING; sai định dạng/không hữu hạn/lẻ/âm/tràn bị từ chối. Zero giữ nguyên zero. Report tách nguồn có value, numeric hợp lệ, mapping giữ nguyên và xác minh độc lập ý nghĩa thị trường (vẫn false).

Envelope 204/No Content đã xác nhận chỉ kết thúc paging OHLC 1m khi không có payload/marker lỗi mâu thuẫn và đã qua kiểm tra metadata/số đếm. Giữ nguyên raw envelope, termination provider_no_content_204. Trang ngắn không rỗng không tự kết thúc; trang lặp, total sai, malformed/lỗi và cắt cụt do giới hạn vẫn fail. --limit chỉ giới hạn in; --full-json giữ các trang raw đã nhận, candidate và diagnostic.

Ngày được cung cấp có 226 hàng unique trên 23 trang không rỗng rồi trang 24, thứ tự giảm dần, 135 nến sáng/90 chiều/một nến 14:45. Đây là quan sát do chủ sở hữu báo cho riêng ngày đó, không phải số count hay công thức chung. Chỉ có hai object candle thật và terminal envelope được cung cấp; replay offline xác minh 2/2, không tái tạo các hàng còn thiếu. Agent live rerun: NOT_RUN (thiếu credential). Bar-start/end, ý nghĩa value/turnover độc lập và completeness thị trường còn chưa xác minh. Ingest tự động/schedule vẫn tắt; inspector preview không đọc/ghi DB. Pilot thủ công riêng được mô tả phía trên.

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

## Master sync — cập nhật 26/10/2026

`sync-master-data` và alias `init` đã dùng orchestrator có guard, mặc định DRY_RUN. Cả bốn dataset SSI v3 hiện BLOCKED; không tự khởi tạo master production. Không nguồn READY thì không gọi API/DB. --write cần đúng một --dataset tường minh và provider READY. Giữ status operator; stock/index mới inactive. Không migration/backfill giá. [Runbook và báo cáo PARTIAL](../src/ingest/master/README.vi.md).
