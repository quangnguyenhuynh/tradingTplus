# Backfill dữ liệu nguồn có guard

[English](README.md)

## Naming và availability

| Canonical | Alias | Trạng thái |
| --- | --- | --- |
| `stock-daily-backfill` | `backfill-daily` | ACTIVE / WRITE như cũ |
| `stock-intraday-backfill` | `backfill-intraday` | GUARDED_OPERATOR / DRY_RUN mặc định |
| `index-daily-backfill` | `index-backfill` | ACTIVE / WRITE như cũ |

Daily/index giữ nguyên runner, JSON flow, default ghi và không thêm --write/--dry-run. Feature backfill là luồng riêng, không bị đổi.

```bash
python main.py stock-daily-backfill --from 01/10/2026 --to 20/10/2026 --symbols SSI HPG --data-source ssi_v3
python main.py index-daily-backfill --from 01/10/2026 --to 20/10/2026 --indexes VNINDEX HNXINDEX --data-source ssi_v3
python main.py stock-intraday-backfill --help
python main.py backfill-intraday --help
```

## Backfill intraday operator có guard

`stock-intraday-backfill` (alias tương thích `backfill-intraday`) nay gọi manual pilot hiện có tuần tự theo range inclusive và symbols tường minh. Mặc định **DRY_RUN**; chỉ `--write` mới persist. `--dry-run`/`--write` loại trừ nhau. Ngày nhận DD/MM/YYYY hoặc YYYY-MM-DD, giữ alias --from-date/--to-date. Không ALL/wildcard/comma scope, universe ngầm, ngày tương lai/range đảo hoặc force overwrite. Normalize/loại trùng symbols giữ thứ tự nhập; ngày tăng dần rồi mã theo thứ tự đó. Chặn quá **50 cặp symbol/weekday** trước service. Cuối tuần không gọi nguồn; range chỉ cuối tuần là OK no-op.

```bash
python main.py stock-intraday-backfill --from 19/10/2026 --to 21/10/2026 --symbols SSI HPG --data-source ssi_v3 --dry-run
# Chỉ owner sau khi đọc dry-run/preflight:
python main.py stock-intraday-backfill --from 19/10/2026 --to 21/10/2026 --symbols SSI HPG --data-source ssi_v3 --write
```

Mỗi cặp tái sử dụng `run_manual_intraday()`: eligibility cả hai status persisted active, paging/map/value SSI v3 toàn ngày, conflict preflight đúng UTC của ngày Việt Nam, chèn raw trước clean không overwrite rồi readback. Không SSI v2, sửa timestamp, ước tính value, lọc bỏ hàng lỗi hoặc ghi đè conflict. Giữ JSON/hash raw và BIGINT `ohlc.value` chính xác; completeness UNVERIFIED, không ép 226 nến. Nguồn rỗng hợp lệ là NO_SOURCE_DATA, không xác nhận holiday hoặc thành công. Ngày lịch sử không hỗ trợ/batch sai được báo rõ. Dry-run không mutation/partition RPC, actual inserts=0 và planned riêng; thiếu DB preflight là BLOCKED, không write-ready.

Conflict/validation lỗi từng cặp được ghi rồi tiếp tục an toàn; lỗi cấu hình/auth/shared dependency đã hết retry thì dừng, giữ completed và unprocessed scope. Không tự retry DB write chưa rõ kết quả. Pair PARTIAL giữ raw đã commit/count được xác nhận và recovery; kiểm tra đúng scope chỉ đọc, xử lý nguyên nhân rồi rerun tường minh. Hàng giống skip, clean thiếu có thể được bổ sung qua guard cũ; không cleanup/delete hoặc hứa atomic xuyên bảng. Range OK khi mọi cặp được xác minh (hoặc không có việc); có verified success lẫn lỗi là PARTIAL; không có cặp success mà có lỗi là FAILED, kể cả đã commit raw dở ở một pair. Pair PARTIAL/count vẫn hiện rõ trong range FAILED. CLI exit 0 chỉ khi OK, 1 cho range lỗi/không xác minh đủ, 2 cho scope/source/argument sai; không đổi exit CLI khác.

JSON range giữ `flow=backfill-intraday`, có planned/processed/OK/blocked/partial/failed/no-source pairs, tổng count, planned insert, halted/unprocessed scope và report pilot trong per_symbol_date. Chỉ giữ summary; batch raw/clean được giải phóng sau mỗi cặp. Registry vẫn preview, không có intraday production factory chung. Stock-intraday một mã/ngày giữ nguyên; intraday-ingest tự động, backfill kết hợp, refill, master và streaming vẫn tắt. Không tự chạy feature/completeness/signal/backtest/alert. Workflow stock-intraday vẫn tắt, không schedule. Không migration hoặc backfill trong phát triển; Codex không ghi live. Xem [manual pilot runbook](../STOCK_INTRADAY_PIPELINE.vi.md) về phục hồi và post-write check chỉ đọc.

## Sau write: chỉ đọc

Owner lưu JSON dry-run/write/rerun; require mọi cặp OK, insert_counts_confirmed=true và consistency_status=PASS ở pair WRITE; rerun actual inserts=0. Xem conflict/failed_stage/recovery, không force sửa lịch sử. Giá trị/timestamp/provenance legacy không được đổi. Raw key `(symbol,time,data_hash)`, clean `(symbol,timeframe,time)` giữ nguyên. Raw source SSI v3 khác hash lịch sử có thể cùng tồn tại theo policy pilot; không tự khẳng định provenance của clean giống có sẵn. Preflight/insert/readback theo từng cặp, không có transaction toàn range/hai bảng. Dry-run thiếu DB chỉ là source preview và range sẽ BLOCKED/halt. Khi nhiều cặp có planned count chưa biết, tổng planned là NULL, không giả là zero.

```bash
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 1m
python scripts/checks/check_ingest.py --date 21/10/2026 --symbols SSI HPG
```

Completeness OK chỉ là structural check, không chứng nhận đủ mọi phút SSI. Empty nguồn không chứng minh holiday. Nếu historical date SSI không hỗ trợ, giữ NO_SOURCE_DATA/error và không chuyển v2. Không cần migration hoặc tự chạy lại dữ liệu lịch sử khi deploy; owner tự chọn scope --write sau review. SSI v3 bar start/end và turnover semantics độc lập chưa được xác minh thêm bởi task này.

## Báo cáo triển khai — 24/10/2026 range intraday có guard

**Trạng thái: COMPLETE cho code và xác minh offline khả thi; owner production-range verification còn chờ.** Đã kiểm tra lại dev `89acaef907b34d7b2df966d4172900035f3b044d` (PR #184). Trước sửa hai tên intraday backfill và runner đều unavailable. Manual pilot được owner xác minh đã có guard nguồn/eligibility/validation/insert-only/readback; task chỉ thêm orchestration giới hạn, không tạo ingest service thứ hai.

Call flow: parser canonical/alias → chuẩn hóa tên cũ → lookup source preview riêng → maintenance handler → run_intraday_backfill_pipeline → run_manual_intraday cho từng cặp explicit → preview adapter/client/mapper/validator SSI v3 hiện có → boundary raw trước clean/readback chỉ khi WRITE. Validate ngày/mã/tổng việc trước client hoặc request; đếm weekday bằng số học trước khi enumerate range đã bound. Tối đa 50 cặp, ngày tăng dần rồi mã normalize theo thứ tự đầu tiên, không song song/background. Giữ flow=backfill-intraday và argument runner public cũ, thêm keyword-only write=False. Chỉ route này exit nonzero với việc partial/unverified; exit lệnh khác không đổi.

Không đổi persistence/mapping pilot. Metadata cần bổ sung: source/validation status, error category đã sanitize, systemic flag; thiếu cấu hình DB được ghi trước fetch để dry-run rỗng/lỗi nguồn cũng không duyệt hoặc tiếp tục plan global không hợp lệ. Range phân biệt EMPTY hợp lệ với lỗi paging, dùng NO_SOURCE_DATA không suy holiday, đổi source-only OK thành blocked/preflight chưa xác minh. Lỗi auth/config/shared dependency dừng và liệt kê NOT_RUN còn lại; source validation/ngày không hỗ trợ/conflict từng cặp được ghi rồi tiếp tục. Không thêm retry HTTP/DB; outcome DB chưa rõ phải rerun tường minh. Không giữ batch raw/clean sau mỗi pair.

Hai alias cùng yêu cầu explicit --symbols, cặp ngày inclusive --from/--to (giữ alias dài), nhận DD/MM/YYYY/ISO, mặc định DRY_RUN, --write/--dry-run loại trừ nhau. Gọi pilot với SSI v3 tường minh kể cả không có option source. Từ chối ALL/wildcard/comma/blank/malformed, ngày tương lai/range đảo, source sai, programmatic write không bool và plan quá 50 trước service. Chỉ cuối tuần là OK không việc, không duyệt ghi. Không force hoặc tự mở universe active.

Guard raw/clean và time/value giữ nguyên: aware market instant/giây → UTC, BIGINT nguồn chính xác, JSON/hash semantic/source ssi_v3, cả hai master status active, paging toàn ngày từ trang 1, không ghi subset rejected/duplicate/mixed. Giữ raw key (symbol,time,data_hash), clean (symbol,timeframe,time), chỉ 1m. Hàng giống skip; raw source/payload/key khác hoặc clean canonical khác/timestamp thừa chặn. Không dịch/sửa timestamp/provenance legacy. Partition RPC chỉ khi write sau validation/preflight, đúng tháng cần. Xác nhận raw trước clean và scoped consistency readback cuối. Không nâng registry production chung, không tự tính feature/completeness/signal/backtest/alert hoặc bật workflow schedule.

### Xác minh

```bash
.venv/bin/python -m pytest -q tests/cli/test_backfill_names.py
.venv/bin/python -m pytest -q tests/cli/test_capability_retirement.py
.venv/bin/python -m pytest -q tests/cli/test_manual_intraday_cli.py
.venv/bin/python -m pytest -q tests/ingest/test_manual_intraday.py
.venv/bin/python -m pytest -q tests/pipeline/test_backfill_pipeline.py
.venv/bin/python -m pytest -q tests/pipeline/test_intraday_backfill.py
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall main.py src scripts tests
git diff --check
.venv/bin/python main.py stock-intraday-backfill --help
.venv/bin/python main.py backfill-intraday --help
```

Suite riêng cuối: CLI backfill names **74 passed**, capability tắt **23 passed**, manual CLI **19 passed**, manual persistence **54 passed**, pipeline backfill cũ **9 passed**, range mới **74 passed**. Full suite cuối **1049 passed, 7 skipped**; compile/help/diff pass. Full run trước edge case cuối thiếu DB/nguồn rỗng đạt 1048/7. Bảy test replacement RPC PostgreSQL cần TEST_DATABASE_URL nên skip; không dùng disposable DB hoặc production write smoke. Task không cần/chạy live read smoke SSI/Supabase; integration nguồn/DB chỉ dùng fake.

Module test mới tái sử dụng fake SSI/PostgREST của pilot và chạy manual path thật sau range wrapper, không sao chép ingest. Cover nhiều mã/ngày/thứ tự, normalize, đúng bound 50 và range cực lớn, cuối tuần/no-op, nguồn rỗng/không hỗ trợ, auth/shared dependency, DB preflight chưa biết, dry-run không write/RPC, cả hai master status, UTC/BIGINT/JSON nguồn, duplicate/mixed/paging/value, legacy conflict/timestamp thừa, raw-before-clean dở và recovery idempotent, tổng count/JSON/exit, scope khác không đổi và không downstream. Chuyển case intraday khỏi kỳ vọng disabled sang routing có guard/safety, giữ coverage combined/refill/các lệnh vẫn tắt.

### File sửa

- `README.md`
- `README.vi.md`
- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/CURRENT_STATE.md`
- `docs/STOCK_INTRADAY_PIPELINE.md`
- `docs/STOCK_INTRADAY_PIPELINE.vi.md`
- `docs/backfill/README.md`
- `docs/backfill/README.vi.md`
- `src/cli/README.md`
- `src/cli/README.vi.md`
- `src/cli/__init__.py`
- `src/cli/maintenance.py`
- `src/cli/parser.py`
- `src/ingest/README.md`
- `src/ingest/README.vi.md`
- `src/ingest/index_daily/README.md`
- `src/ingest/index_daily/README.vi.md`
- `src/ingest/maintenance/README.md`
- `src/ingest/maintenance/README.vi.md`
- `src/ingest/maintenance/backfill.py`
- `src/ingest/master/README.md`
- `src/ingest/master/README.vi.md`
- `src/ingest/stock_daily/README.md`
- `src/ingest/stock_daily/README.vi.md`
- `src/ingest/stock_intraday/README.md`
- `src/ingest/stock_intraday/README.vi.md`
- `src/ingest/stock_intraday/manual.py`
- `src/ingest/streaming/README.md`
- `src/ingest/streaming/README.vi.md`
- `src/ingest/workflows/README.md`
- `src/ingest/workflows/README.vi.md`
- `tests/cli/test_backfill_names.py`
- `tests/cli/test_capability_retirement.py`
- `tests/pipeline/test_backfill_pipeline.py`

### File tạo

- `tests/pipeline/test_intraday_backfill.py`

### Tác động DB và rủi ro

Migration/schema/contract: **NONE**. Dữ liệu production đổi trong dev/test: **NONE**. Không chạy historical backfill hoặc yêu cầu tự động khi deploy. Khi owner --write sau review, có thể chèn hàng đã xác minh vào hai bảng hiện có và tạo partition tháng cần qua RPC cũ. Conflict giữ nguyên; không delete/replace/cleanup/relabel lịch sử. Không đổi formula/feature backfill. Daily/index backfill không đổi.

**No live SSI production ingestion or Supabase database writes occurred during implementation or verification.**

Runtime vẫn cần SSI hỗ trợ lịch sử, master active, credential local hợp lệ, unique/RPC permission và partition phù hợp. Weekday nguồn rỗng không chứng nhận holiday; bar start/end, turnover semantics độc lập và coverage thị trường vẫn UNVERIFIED. Writer khác có thể đổi evidence sau readback; chọn thời điểm operator không có writer. Không có transaction toàn range hoặc xuyên hai bảng. Nếu raw commit dở mà chưa pair nào hoàn tất, range FAILED nhưng partial_pairs/raw_inserted/insert_counts_confirmed/recovery hiện rõ. Request lỗi có thể đã commit ngoài count được xác nhận. Xem đúng scope/conflict trước rerun, rồi insert-ignore cùng scope để hoàn tất clean khi guard cho phép. Planned chưa biết/chưa xử lý giữ tổng planned insert NULL.

### Lệnh owner và bước tiếp

Chạy ví dụ dry-run ở trên trước. Chỉ owner sau khi xem preflight mọi cặp mới chạy ví dụ --write. Lưu JSON dry-run/write/rerun, require tất cả pair OK, WRITE readback PASS được xác nhận, lần lặp actual insert=0. Chạy Phase 0/completeness chỉ đọc ở trên; structural OK không chứng nhận mọi phút. Không tự active mã hoặc sửa conflict legacy. Bước tiếp: owner xác minh scope lịch sử nhỏ có dữ liệu và rerun an toàn sau merge; unattended/incremental/scheduled cần task riêng. Codex không được thực thi production trong task này.

> Báo cáo naming bên dưới là lịch sử 23/10. Trạng thái DISABLED của intraday trong báo cáo đó đã được thay bằng contract operator có guard ở trên.

## Báo cáo triển khai — 23/10/2026

**Trạng thái: COMPLETE.** Đã kiểm tra lại dev `d81e0eff1bb63c7234c3a2c10cdfd88ace29ef17` (PR #183). CLI trước đây trộn tên stock dạng tiền tố backfill và index-backfill; nay có tên canonical theo dataset, giữ toàn bộ alias cũ. Runbook cũ còn mô tả intraday/combined/refill đang chạy và hỗ trợ SSI v2 tường minh; bản trên sửa đúng trạng thái hiện tại, không đổi khả năng thực thi code.

Triển khai: parser đăng ký canonical kèm argparse aliases, giữ argument action/default. Main CLI chỉ chuẩn hóa stock-daily-backfill → backfill-daily, stock-intraday-backfill → backfill-intraday, index-daily-backfill → index-backfill trước source preflight/disabled guard/dispatch. Handler maintenance/index và runner public giữ nguyên. Không sửa ingest/API/DB/validation/feature/thuật toán backfill; giữ flow JSON, exit convention và không in cảnh báo deprecation lên stdout.

Source preflight intraday backfill tường minh resolve đúng stock_intraday thay vì stock_daily, dùng lookup nonproduction không tạo adapter. Source ssi_v3 vẫn bị guard NOT_IMPLEMENTED/exit 1; ssi_v2 không hỗ trợ vẫn exit 2. Không source vẫn chặn trước handler. Hai tên đều unavailable; combined backfill/refill/intraday-ingest/streaming-ingest vẫn tắt. Không đổi manual pilot stock-intraday, lệnh feature, registry readiness hoặc schedule. Daily/index tên mới/cũ gọi cùng runner với ngày/source/default scope giống nhau; giữ khác biệt normalize stock/index hiện có.

### Lệnh test và kết quả

```bash
.venv/bin/python -m pytest -q tests/cli/test_cli_refactor.py
.venv/bin/python -m pytest -q tests/cli/test_capability_retirement.py
.venv/bin/python -m pytest -q tests/pipeline/test_backfill_pipeline.py
.venv/bin/python -m pytest -q tests/ingest/test_index_daily_pipeline.py
.venv/bin/python -m pytest -q tests/cli/test_backfill_names.py
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall main.py src scripts tests
.venv/bin/python main.py --help
.venv/bin/python main.py stock-daily-backfill --help
.venv/bin/python main.py stock-intraday-backfill --help
.venv/bin/python main.py index-daily-backfill --help
.venv/bin/python main.py backfill-daily --help
.venv/bin/python main.py backfill-intraday --help
.venv/bin/python main.py index-backfill --help
git diff --check
```

Bốn suite bắt buộc hiện có pass lần lượt **25 / 25 / 10 / 16**; capability suite thêm case tên canonical bị tắt. Test mới naming/routing/help/docs: **74 passed**. Full regression: **978 passed, 7 skipped**. Compile/diff và bảy help invocation pass offline. Bảy test replacement RPC PostgreSQL hiện có skip vì TEST_DATABASE_URL chưa cấu hình. Không thử live backfill, fetch nguồn hay xác minh DB; runner active dùng fake và guard client/service/manual pilot. Các giả định test ban đầu về wrap help alias/cách viết index đã sửa theo hành vi thật; test cuối pass.

Test mới cover parser canonical/legacy, alias cận ngày, required bounds/flag sai, dataset/source rejection, scope/source mặc định, argument runner và flow JSON, exit OK/PARTIAL/FAILED giữ nguyên, help không credential và intraday chặn trước handler/manual/API/DB. Regression CLI, manual pilot, Daily/Index/features, disabled capability và backfill cũ tiếp tục pass.

### File sửa

- `README.md`
- `README.vi.md`
- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/STOCK_INTRADAY_PIPELINE.md`
- `docs/STOCK_INTRADAY_PIPELINE.vi.md`
- `docs/backfill/README.md`
- `docs/backfill/README.vi.md`
- `src/cli/README.md`
- `src/cli/README.vi.md`
- `src/cli/__init__.py`
- `src/cli/parser.py`
- `src/ingest/README.md`
- `src/ingest/README.vi.md`
- `src/ingest/index_daily/README.md`
- `src/ingest/index_daily/README.vi.md`
- `src/ingest/maintenance/README.md`
- `src/ingest/maintenance/README.vi.md`
- `src/ingest/master/README.md`
- `src/ingest/master/README.vi.md`
- `src/ingest/stock_daily/README.md`
- `src/ingest/stock_daily/README.vi.md`
- `src/ingest/stock_intraday/README.md`
- `src/ingest/stock_intraday/README.vi.md`
- `src/ingest/streaming/README.md`
- `src/ingest/streaming/README.vi.md`
- `src/ingest/workflows/README.md`
- `src/ingest/workflows/README.vi.md`
- `tests/cli/test_capability_retirement.py`

### File tạo

- `tests/cli/test_backfill_names.py`

### Tác động DB, rủi ro và bước tiếp

Migration/schema/bảng/dữ liệu thay đổi: **NONE**. Cần backfill: **NO**. Không chạy migration. Không đổi module Python ingest, provider/DB/feature hoặc workflow; chỉ cập nhật README song ngữ liên quan. Quyết định kiến trúc/evidence report lịch sử giữ tên cũ dưới nghĩa lịch sử/alias vẫn tương thích.

**No live SSI ingestion or Supabase database writes were executed.**

Giới hạn chủ ý: intraday backfill chỉ có tên dự phòng, chưa triển khai; flow JSON giữ tên legacy, không suy từ tên CLI mới. Daily/index active vẫn ghi theo contract hiện có và không thêm cờ dry-run/write. Live backfill ngoài phạm vi, không nhận là đã xác minh. Bước tiếp: review/merge PR chỉ đổi naming này, ưu tiên canonical trong hướng dẫn operator mới, giữ alias, và cần task/ủy quyền riêng trước intraday range ingest. Không cần chạy lại production để dùng tên mới.
