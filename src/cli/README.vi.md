# src/cli — parser và điều phối

## Backfill intraday operator có guard

`stock-intraday-backfill` (alias tương thích `backfill-intraday`) nay gọi manual pilot hiện có tuần tự theo range inclusive và symbols tường minh. Mặc định **DRY_RUN**; chỉ `--write` mới persist. `--dry-run`/`--write` loại trừ nhau. Ngày nhận DD/MM/YYYY hoặc YYYY-MM-DD, giữ alias --from-date/--to-date. Không ALL/wildcard/comma scope, universe ngầm, ngày tương lai/range đảo hoặc force overwrite. Normalize/loại trùng symbols giữ thứ tự nhập; ngày tăng dần rồi mã theo thứ tự đó. Chặn quá **50 cặp symbol/weekday** trước service. Cuối tuần không gọi nguồn; range chỉ cuối tuần là OK no-op.

```bash
python main.py stock-intraday-backfill --from 19/10/2026 --to 21/10/2026 --symbols SSI HPG --data-source ssi_v3 --dry-run
# Chỉ owner sau khi đọc dry-run/preflight:
python main.py stock-intraday-backfill --from 19/10/2026 --to 21/10/2026 --symbols SSI HPG --data-source ssi_v3 --write
```

Mỗi cặp tái sử dụng `run_manual_intraday()`: eligibility cả hai status persisted active, paging/map/value SSI v3 toàn ngày, conflict preflight đúng UTC của ngày Việt Nam, chèn raw trước clean không overwrite rồi readback. Không SSI v2, sửa timestamp, ước tính value, lọc bỏ hàng lỗi hoặc ghi đè conflict. Giữ JSON/hash raw và BIGINT `ohlc.value` chính xác; completeness UNVERIFIED, không ép 226 nến. Nguồn rỗng hợp lệ là NO_SOURCE_DATA, không xác nhận holiday hoặc thành công. Ngày lịch sử không hỗ trợ/batch sai được báo rõ. Dry-run không mutation/partition RPC, actual inserts=0 và planned riêng; thiếu DB preflight là BLOCKED, không write-ready.

Conflict/validation lỗi từng cặp được ghi rồi tiếp tục an toàn; lỗi cấu hình/auth/shared dependency đã hết retry thì dừng, giữ completed và unprocessed scope. Không tự retry DB write chưa rõ kết quả. Pair PARTIAL giữ raw đã commit/count được xác nhận và recovery; kiểm tra đúng scope chỉ đọc, xử lý nguyên nhân rồi rerun tường minh. Hàng giống skip, clean thiếu có thể được bổ sung qua guard cũ; không cleanup/delete hoặc hứa atomic xuyên bảng. Range OK khi mọi cặp được xác minh (hoặc không có việc); có verified success lẫn lỗi là PARTIAL; không có cặp success mà có lỗi là FAILED, kể cả đã commit raw dở ở một pair. Pair PARTIAL/count vẫn hiện rõ trong range FAILED. CLI exit 0 chỉ khi OK, 1 cho range lỗi/không xác minh đủ, 2 cho scope/source/argument sai; không đổi exit CLI khác.

JSON range giữ `flow=backfill-intraday`, có planned/processed/OK/blocked/partial/failed/no-source pairs, tổng count, planned insert, halted/unprocessed scope và report pilot trong per_symbol_date. Chỉ giữ summary; batch raw/clean được giải phóng sau mỗi cặp. Registry vẫn preview, không có intraday production factory chung. Stock-intraday một mã/ngày giữ nguyên; intraday-ingest tự động, backfill kết hợp, refill, master và streaming vẫn tắt. Không tự chạy feature/completeness/signal/backtest/alert. Workflow stock-intraday vẫn tắt, không schedule. Không migration hoặc backfill trong phát triển; Codex không ghi live. Xem [runbook](../../docs/backfill/README.vi.md) về phục hồi và post-write check chỉ đọc.

Tên CLI canonical và alias tương thích (không có lịch bỏ alias): `stock-daily-backfill` → `backfill-daily`; `stock-intraday-backfill` → `backfill-intraday`; `index-daily-backfill` → `index-backfill`. Giữ tên CLI tương thích; daily/index không đổi. Intraday dùng contract range operator có guard. Stock Daily/Index Daily backfill ACTIVE / WRITE; Stock Intraday backfill có guard, chỉ operator, mặc định DRY_RUN, ghi cần --write và tối đa 50 cặp weekday; luồng tự động vẫn tắt.

[English](README.md)


## Pilot intraday thủ công có guard

`stock-intraday` hỗ trợ đúng một mã và ngày giao dịch Việt Nam tường minh. Mặc định/`--dry-run` là READ-ONLY; chỉ `--write` mới cho phép chuỗi chèn raw → clean có kiểm soát. Cần credential SSI; credential service Supabase cho phép preflight chỉ đọc eligibility/xung đột và bắt buộc khi ghi. Nếu chưa cấu hình DB, dry-run báo `NOT_RUN_NO_CREDENTIALS`, số dự kiến chưa biết và `write_ready=false`.

```bash
python main.py stock-intraday 20/10/2026 --symbols SSI
python main.py stock-intraday 20/10/2026 --symbols SSI --write
```

Lệnh thứ hai **chỉ dành cho chủ sở hữu sau khi kiểm tra dry-run/preflight**. Không nhận khoảng ngày, ALL/wildcard, scope thiếu, nhiều mã hoặc ngày tương lai. Cả hai status trong master phải active. Chỉ nguồn `ssi_v3`, timeframe `1m`; value canonical giữ chính xác `ohlc.value`, thiếu/sai sẽ chặn pilot và không ước tính bù. Hàng giống giữ nguyên; clean khác giá trị hoặc raw xung đột key/source/payload sẽ chặn. Không force overwrite. Xác nhận raw trước clean; ghi dở dang/không rõ kết quả trả exit khác 0, cần kiểm tra đúng scope rồi chạy lại an toàn. Không cam kết transaction xuyên hai bảng. Completeness vẫn UNVERIFIED. Intraday-ingest tự động, backfill kết hợp, refill, streaming và schedule vẫn tắt. Pilot không chạy feature/signal/backtest.

Xem [runbook](../../docs/STOCK_INTRADAY_PIPELINE.vi.md) về thứ tự ghi, idempotency, partition, phục hồi và xác minh của chủ sở hữu. Inspector vẫn hoàn toàn chỉ đọc; registry giữ preview, không có factory production chung.

`parser.py` định nghĩa tham số; `__init__.py` parse trước, kiểm tra source/capability trước khi nạp handler domain. Help không gọi dịch vụ. `stock`, `index`, `features`, `foreign`, `screener`, `analogs`, `maintenance`, `streaming` chỉ điều phối, không trộn công thức hay tự bật nguồn tắt. `common.py` in summary và map FAILED thành exit 1; ValueError thành 2, PARTIAL có thể 0.

Các nhóm lệnh còn tắt dưới giữ parser nhưng dừng trước khi nạp handler hoặc tạo client SSI/DB. Trả exit 1 và JSON status FAILED, error_type NOT_IMPLEMENTED. Source tường minh bị từ chối có thể trả exit 2 ở preflight trước đó. Help vẫn mô tả mục đích cũ, không chứng minh khả năng chạy.

| Lệnh | Mục đích trước đây | Adapter / dataset cần trong tương lai |
| --- | --- | --- |
| sync-master-data, init | Đồng bộ master idempotent | Adapter master v3 được xác minh, giữ status operator; master |
| intraday-ingest | Ingest raw/clean nguồn 1m | Adapter v3 1m, pagination, timestamp, đơn vị đã xác minh; stock_intraday |
| backfill | Daily/intraday kèm check | Cùng adapter; stock_intraday; không chạy riêng phần daily |
| refill | Nguồn/check/feature một mã | Cùng adapter; stock_intraday; không chạy riêng daily/feature |
| streaming-ingest | Streaming giới hạn, ghi tùy chọn | Adapter protocol/auth/capture v3 đã xác minh; streaming |

Chụp orderbook cũng tắt đến khi có adapter streaming được xác minh; không tự tạo endpoint REST depth công khai. Raw/clean/master/feature/streaming lịch sử vẫn còn và dùng được theo contract. Gọi lệnh đang tắt không fallback, xóa hay sửa lịch sử. Dưới đây chỉ là help, không phải ví dụ chạy production thành công.

```bash
python main.py --help
python main.py features-daily --help
python main.py stock-eod 19/10/2026 --symbols SSI
python main.py foreign-rank --date 19/10/2026 --ranking emerging --window 5 --top 20
```

[Danh mục tất cả lệnh, tham số, alias, default và ví dụ](../../docs/CLI_USAGE.vi.md)
