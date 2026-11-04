# Audit và chuẩn hóa numeric/decimal cho SSI v3 daily

[English](DAILY_NUMERIC_PRECISION.md)

## Điều tra và bằng chứng

Base `dev`: `7eb92be8a67c543a33865b7d3f1d044b4473beed` (đã merge PR #190). Đã đọc contracts/registry/transforms/engine/derived, luồng stock/index, adapter/REST, validator daily, RPC V1/migrations, catalog DB thực tế, CLI/inspector và tests trước khi sửa.

Lỗi xác nhận: tiền Stock dùng int và integer check V1 loại phần lẻ; Index cùng validator daily dùng float; decoder HTTP/SDK có thể làm tròn trước mapper; SDK JSON thông thường không nhận Decimal nguyên bản; Decimal context mặc định 28 có thể làm tròn derived; tolerance tương đối Index có thể che sai lệch tiền; SQL V1 buộc tiền cũ phải nguyên khi giữ lại; Index cho thiếu level bắt buộc, chưa enforce count nguyên và có thể overwrite cùng key khi trả nhiều row.

Catalog chỉ đọc xác nhận các cột thị trường daily là NUMERIC không typmod scale. CLEAN key stock `(symbol,trading_date)`, index `(index_code,trading_date)`; RAW stock có source/hash, RAW index dùng `(index_code,trading_date,data_hash)`. RPC Stock V1 đã có trên DB dưới SECURITY INVOKER; log Stock có unique current identity. Không thấy index_data_quality_logs, validation_status hoặc source/raw/audit trên Index CLEAN. Không apply thay đổi schema ở production.

SELECT đúng scope ngày 04/11/2026 (Việt Nam):

| Mã/ngày | RAW totalMatchValue dạng JSON string | CLEAN total_match_val |
| --- | --- | --- |
| BID / 12/03/2025 | 162662895000.001 | thiếu |
| TCB / 12/03/2025 | 303651874999.999 | thiếu |
| VCB / 12/03/2025 | 506132139999.992 | thiếu |
| TCB / 29/04/2025 | 478199435000.012 | thiếu |

| VNINDEX/ngày | v3 RAW netPurchasesForeignValue | CLEAN |
| --- | --- | --- |
| 17/03/2026 | -669526974313.6 | -669526974313.6 |
| 28/07/2026 | -1978131345916.1 | -1978131345916.1 |
| 07/08/2026 | -76067038810.7 | -76067038810.7 |

Ba mẫu Index khớp chính xác theo SQL numeric. Cùng ngày còn RAW legacy SSI_DailyIndex không có field v3 này: đây là khác biệt provenance, không chứng minh Index lịch sử đã hỏng. Chưa tính lại toàn lịch sử các số owner báo 418 RAW phần lẻ, 219 RAW-only key, 17 mẫu Index hoặc số ngày VNIndex/VNINDEX; đây không phải hằng acceptance. Phải tính lại đúng scope trước backfill.

Fixture dùng hình dạng payload v3 có sẵn cùng giá trị tiền đã xác nhận. OHLC/field khác lấy từ mẫu SSI có sẵn để minh họa, không nhận là toàn payload BID/TCB/VCB chép nguyên bản.

## Phân loại và version

Contract/mapping daily **3.0.0**, Stock policy **stock_daily_validation_v1.1.0**, Index validator **index_daily_numeric_v1.0.0**. Giữ tên/signature hàm và tên CLI EOD. Canonical tiền/giá daily nay là Decimal, quantity rời rạc là int. Consumer pin version cũ phải chủ động cập nhật; registry phục vụ declaration hiện tại, còn report/log cũ vẫn giữ version gốc để đọc.

NUMERIC PostgreSQL lưu decimal chính xác, không chứng minh float Python giữ đủ chữ số nguồn. Tiền nhận phần lẻ hữu hạn, không round/truncate/đổi scale/điền 0. Quantity yêu cầu nguyên chính xác. Change/net cho phép âm đúng field. Giữ nguyên đơn vị/phần trăm. Field chưa hỗ trợ vẫn NULL, không dựng mapping.

Bảng dưới liệt kê mọi field numeric; cột SQL vẫn NUMERIC. Stock OHLC luôn dương dù match bằng 0 hoặc thiếu; không dựng giá ngày không giao dịch. Match thiếu vẫn NULL + PARTIAL theo nullable contract. Average optional giữ rule zero theo hoạt động giao dịch hiện có. `signed` là cho phép âm; `mandatory` là bắt buộc; `derived` là tính từ input; `unsupported` là chưa có mapping nguồn xác nhận.

### stock_daily

| Field | Unit | Semantics | Sign / required policy | Transform |
| --- | --- | --- | --- | --- |
| `price_change` | VND/share | level_price_percentage | signed | decimal |
| `per_price_change` | percent | level_price_percentage | signed | decimal |
| `ceiling_price` | VND/share | level_price_percentage | >= 0; optional | unsupported -> NULL |
| `floor_price` | VND/share | level_price_percentage | >= 0; optional | unsupported -> NULL |
| `ref_price` | VND/share | level_price_percentage | >= 0; optional | unsupported -> NULL |
| `open_price` | VND/share | level_price_percentage | > 0; mandatory | decimal |
| `highest_price` | VND/share | level_price_percentage | > 0; mandatory | decimal |
| `lowest_price` | VND/share | level_price_percentage | > 0; mandatory | decimal |
| `close_price` | VND/share | level_price_percentage | > 0; mandatory | decimal |
| `average_price` | VND/share | level_price_percentage | existing optional price rule | decimal |
| `close_price_adjusted` | VND/share | level_price_percentage | >= 0; optional | unsupported -> NULL |
| `total_match_vol` | shares | discrete_quantity | >= 0 when present; NULL -> PARTIAL | exact_int |
| `total_match_val` | VND | monetary | >= 0 when present; NULL -> PARTIAL | decimal |
| `total_deal_vol` | shares | discrete_quantity | >= 0; optional | exact_int |
| `total_deal_val` | VND | monetary | >= 0; optional | decimal |
| `total_traded_vol` | shares | discrete_quantity | >= 0; optional | derived exact_int |
| `total_traded_value` | VND | monetary | >= 0; optional | derived decimal |
| `foreign_buy_vol_total` | shares | discrete_quantity | >= 0; optional | exact_int |
| `foreign_sell_vol_total` | shares | discrete_quantity | >= 0; optional | exact_int |
| `foreign_buy_val_total` | VND | monetary | >= 0; optional | decimal |
| `foreign_sell_val_total` | VND | monetary | >= 0; optional | decimal |
| `foreign_remaining_room` | shares | discrete_quantity | >= 0; optional | exact_int |
| `foreign_total_room` | shares | discrete_quantity | >= 0; optional | exact_int |
| `net_foreign_vol` | shares | discrete_quantity | signed | derived exact_int |
| `net_foreign_val` | VND | monetary | signed | derived decimal |
| `total_buy_trade` | trades | discrete_quantity | >= 0; optional | exact_int |
| `total_buy_trade_vol` | shares | discrete_quantity | >= 0; optional | exact_int |
| `total_sell_trade` | trades | discrete_quantity | >= 0; optional | exact_int |
| `total_sell_trade_vol` | shares | discrete_quantity | >= 0; optional | exact_int |

### index_daily

| Field | Unit | Semantics | Sign / required policy | Transform |
| --- | --- | --- | --- | --- |
| `index_value` | index points | level_price_percentage | > 0; mandatory | decimal |
| `index_change` | index points | level_price_percentage | signed | decimal |
| `index_change_percentage` | percent | level_price_percentage | signed | decimal |
| `total_trade_volume` | provider volume | discrete_quantity | >= 0; optional | exact_int |
| `total_trade_value` | provider value | monetary | >= 0; optional | decimal |
| `total_match_volume` | provider volume | discrete_quantity | >= 0; optional | exact_int |
| `total_match_value` | provider value | monetary | >= 0; optional | decimal |
| `total_deal_volume` | provider volume | discrete_quantity | >= 0; optional | exact_int |
| `total_deal_value` | provider value | monetary | >= 0; optional | decimal |
| `total_advance_stock` | stocks | discrete_quantity | >= 0; optional | exact_int |
| `total_ceiling_stock` | stocks | discrete_quantity | >= 0; optional | exact_int |
| `total_decline_stock` | stocks | discrete_quantity | >= 0; optional | exact_int |
| `total_floor_stock` | stocks | discrete_quantity | >= 0; optional | exact_int |
| `total_no_change_stock` | stocks | discrete_quantity | >= 0; optional | exact_int |
| `total_prop_buy_volume` | provider volume | discrete_quantity | >= 0; optional | exact_int |
| `total_prop_buy_value` | provider value | monetary | >= 0; optional | decimal |
| `total_prop_sell_volume` | provider volume | discrete_quantity | >= 0; optional | exact_int |
| `total_prop_sell_value` | provider value | monetary | >= 0; optional | decimal |
| `total_foreign_buy_volume` | provider volume | discrete_quantity | >= 0; optional | exact_int |
| `total_foreign_buy_value` | provider value | monetary | >= 0; optional | decimal |
| `total_foreign_sell_volume` | provider volume | discrete_quantity | >= 0; optional | exact_int |
| `total_foreign_sell_value` | provider value | monetary | >= 0; optional | decimal |
| `net_foreign_purchase_volume` | provider volume | discrete_quantity | signed | exact_int |
| `net_foreign_purchase_value` | provider value | monetary | signed | decimal |

## Mapping, arithmetic và transport chính xác

Hai transform allowlist mới `decimal`/`exact_int` reject bool, NaN/Infinity và string không hợp lệ. Integer kiểm integrality bằng Decimal trước int. Alias so sánh theo giá trị toán học; alias khác nhau hoặc lỗi alias mơ hồ vẫn reject. Không thêm multiplier/đổi đơn vị ngầm.

Chỉ mapping daily opt in; không sửa to_int/to_float legacy hoặc intraday/master/features. Không mapping hiện tại nào còn dùng transform int legacy. Hàm cũ vẫn tồn tại để giữ compatibility và không nằm trên đường daily mới.

HTTP daily production parse bytes gốc với parse_float=Decimal, integer JSON vẫn chính xác. Reject duplicate key và nonfinite JSON constant. HTTP daily của Inspector cùng JSON renderer giữ numeric token. Input đã bị decoder khác đổi sang float chỉ giữ được Decimal(str(float)), không phục hồi chữ số đã mất; report ghi predecoded_float_source_fields và mapped predecoded_float_fields. Field mapped đã là float tạo WARNING PREDECODED_FLOAT_PRECISION_UNVERIFIED (Stock PARTIAL, Index warning); không coi việc đổi kiểu là phục hồi precision. RAW lịch sử đã làm tròn trước lưu không thể chứng minh số gốc nếu thiếu evidence nguồn mới.

Derived Stock dùng local Decimal precision tính theo operand, không phụ thuộc context 28. NULL truyền sang derived. SQL tính lại từ input cuối sau retention. Không float, quantize hoặc tolerance làm tròn tiền/quantity. Giữ các tolerance giá/change Stock legacy; không nhận đây là tick/precision rule SSI mới đã xác minh.

Luồng ghi: bytes SSI -> RAW semantic bất biến -> mapper/policy/derived chính xác -> JSON numeric token bên trong **tham số RPC text** -> PostgreSQL cast ::jsonb/NUMERIC -> readback. SDK chỉ encode string/metadata bên ngoài, không đổi Decimal sang float hoặc thay số RAW thành string. String nguồn vẫn string, số JSON vẫn số. Không monkey-patch SDK hoặc thêm dependency.

RAW là JSONB semantic, không archive whitespace/format bytes HTTP. Payload string có hash canonical giống trước. Decoder số chính xác có thể tạo hash mới khi representation cũ đã làm tròn hoặc khác lexical scale: đây là version RAW riêng, không sửa RAW cũ. Rerun cùng exact payload vẫn deterministic. Index RAW có conflict key không gồm source; nếu cùng hash va vào provenance khác, readback fail và giữ nguyên evidence legacy thay vì overwrite.

## Stock V1 và quality logs

Identity/OHLC/match có giá trị sai vẫn reject. Giữ allowlist/quarantine V1: room âm NULL + BELOW_MINIMUM; quantity optional lỗi thành NULL, không lưu share lẻ. Match volume lẻ bắt buộc reject. Tiền có phần lẻ hữu hạn không âm được giữ nguyên và WARNING FRACTIONAL_MONETARY_VALUE, action KEEP_EXACT_DECIMAL, nên PARTIAL. Warning phản ánh precision semantics cần xác minh, không kết luận phần lẻ là sai. Chỉ cảnh báo input tiền mapped; derived kế thừa evidence input.

RPC persist_stock_daily_validation_v1 giữ identity và transaction CLEAN/log. Rule giữ tiền cũ nay cho decimal hữu hạn không âm; quantity vẫn nguyên. Wrapper text mới gọi lại RPC này. Nhận policy 1.0.0 cho app cũ và 1.1.0 cho app tương ứng; không trộn writer lúc deploy. REJECTED không overwrite CLEAN, PARTIAL không downgrade VALID. Attempt phần lẻ mới gặp CLEAN VALID trả CLEAN_VALID_DOWNGRADE_BLOCKED để owner review, không force qua guard.

Current identity vẫn `(symbol,trading_date,check_name='stock_daily_validation_v1')`, timeframe 1d. Fingerprint gồm RAW/policy/decision/issues; prior snapshot khác được thêm history một lần; replay giống nhau không tăng bản sao vô hạn. REJECTED 1.0.0 vẫn đọc được trong history khi 1.1.0 chấp nhận PARTIAL. VALID không issue không tạo log mới, resolve issue cũ. Status NULL lịch sử vẫn chưa xác minh. Input cũ hợp lệ có thể giữ khi payload mới thiếu, với KEEP_EXISTING_FIELD/preserved_fields/previous_clean_raw_hash; không giữ giá trị legacy sai. Derived luôn tính lại, không báo đã giữ nếu thực tế không giữ. previous_clean_raw_hash chỉ được ghi khi đúng một RAW khớp semantic JSONB; nhiều version tương đương số thì hash để NULL và previous_clean_raw_hash_match_count ghi mức mơ hồ, không chọn LIMIT 1 tùy ý.

RAW commit trước; CLEAN/log atomic sau, có readback và không retry write mơ hồ. Ack/log/readback lỗi báo failure; RAW có thể còn. Mất HTTP ack có thể xảy ra sau commit, phải reconcile trước rerun. Error summary chỉ đúng migration mới nếu thiếu RPC. Giữ counters/backfill aggregation V1.

## Rule riêng cho Index

Pipeline Index độc lập. Level hữu hạn dương, ngày request đúng và identity nhất quán là bắt buộc. Endpoint v3 có thể không trả code; context index request tiếp tục là nguồn identity hiện có. Nếu payload có index/indexCode/indexId thì phải khớp sau uppercase. Case-only được so sánh cùng mã, không sửa RAW. Nhiều record source thì giữ RAW nhưng reject mọi CLEAN mơ hồ.

Field numeric có giá trị phải hữu hạn; volume/count nguyên; total/buy/sell không âm; change/net có thể âm. Lỗi numeric core hoặc optional đều reject toàn row Index. **Chưa thêm quarantine optional cho Index**: chưa có contract log/status phù hợp; không tạo framework log song song hoặc dùng log Stock sai identity. Tiền phần lẻ tự nó vẫn hợp lệ theo semantics tiền Index hiện có; không đồng nghĩa SSI precision/completeness đã được kiểm chứng độc lập.

Total = match + deal, net = buy - sell so sánh chính xác với tolerance số bằng **0**. Lệch tạo warning có giải thích, giữ nguyên số nguồn, không tính lại total để ép pass. Có warning thì CLI PARTIAL. RPC Index serialize `(index_code,date)`, giữ input cũ hợp lệ khi mới NULL, readback và trả preserved_fields. Recheck consistency sau merge, trả merge_issues với giá trị string decimal chính xác để giải thích provenance trộn. Input reject không gọi CLEAN RPC. Index CLEAN không có status hoặc hash RAW persist; current/resolved warnings không được lưu bền cho Index. Export summary/audit; đánh dấu validation/provenance lịch sử UNVERIFIED.

## Diagnostic chỉ đọc

Lệnh mới chỉ đọc dữ liệu đã lưu qua read_daily_numeric_scope_v1, STABLE SECURITY INVOKER SELECT, trả JSON **text** để SDK không parse float trước khi audit dùng Decimal. Không SSI, không ghi RAW/CLEAN/log/features và không fallback sang table read mất precision.

```bash
python main.py daily-numeric-quality --dataset stock_daily --identifiers BID TCB VCB --date 12/03/2025 > stock-20250312-quality.json
python main.py daily-numeric-quality --dataset stock_daily --identifiers TCB --date 29/04/2025
python main.py daily-numeric-quality --dataset index_daily --identifiers VNINDEX --date 17/03/2026
python main.py daily-numeric-quality --dataset index_daily --identifiers VNINDEX --from 28/07/2026 --to 07/08/2026 > vnindex-quality.json
```

Giới hạn 1–50 mã tường minh, 31 ngày lịch, page 100 row, cap 10.000 row cho từng kind. Scope sai fail trước DB client. Kiểm identity/order/count ổn định, duplicate/count đổi/truncated đều fail; thu hẹp scope khi lỗi. Các page là quan sát đọc riêng, không phải snapshot transaction chung; pause writer nếu cần đối soát authoritative.

Report phân loại RAW-only/CLEAN-only, chênh lệch số giữa version, phần lẻ tiền hợp lệ, quantity không nguyên, sign/mapping/validation error, optional thiếu, case/provenance conflict, CLEAN lịch sử chưa xác minh, current/resolved Stock issues và history. Count theo dataset/source/mã canonical/ngày/field/code/mapping/policy version. Một RAW có nhiều observation; nhiều version RAW không phải nhiều ngày giao dịch. Legacy source không được remap thành v3. VNIndex/VNINDEX chỉ canonicalize khi so sánh, không rename/merge RAW. Nhiều CLEAN khác case cùng canonical key được đánh dấu mơ hồ.

Mismatch chỉ là quan sát, chưa chứng minh corruption: CLEAN có thể thuộc RAW khác hoặc input cũ được giữ. Stock có clean_matches_this_raw và log provenance; Index không đủ schema để chứng minh. Replay RAW không dựng lại lỗi HTTP/DB/log/context nhiều record cũ. Financial observation của CLI dùng decimal string khi cần; Inspector/index-preview giữ JSON numeric token. Dùng reader Decimal-aware khi parse JSON số. stock-eod-quality cũ vẫn hoạt động nhưng dùng SDK decoder cũ; precision note hướng audit chính xác sang lệnh mới.

## Owner migration, kiểm tra và rollback

Migration mới [`20261104_daily_numeric_precision.sql`](../migrations/20261104_daily_numeric_precision.sql). Không sửa migration đã áp dụng 20261103_stock_daily_quality_v1.sql. Local không có Supabase CLI nên tạo file thủ công theo date-prefix hiện có của repo.

Replace RPC Stock V1 và thêm bốn hàm: persist_daily_raw_numeric_v1, persist_stock_daily_numeric_v1, persist_index_daily_numeric_v1, read_daily_numeric_scope_v1. Tất cả invoker, search_path rỗng, revoke PUBLIC/anon/authenticated execute, grant service_role. Không bảng/cột/status/index mới, không đổi NUMERIC, không rewrite market/status lịch sử hoặc backfill. NOTIFY reload schema cache PostgREST. Lock timeout migration 5 giây; owner tự apply.

Thứ tự: review PR/SQL -> pause cả hai daily writer và drain run -> owner apply sau V1 -> kiểm catalog/quyền/schema cache -> deploy app tương ứng -> diagnostic chỉ đọc -> owner chọn một Stock rerun thử -> kiểm CLEAN/status/log chính xác -> chỉ test Index write nếu audit có lý do -> mới lập scope lịch sử tiếp theo. App mới trước migration sẽ fail; không trộn writer cũ/mới. Unit test không chứng minh production API đã deploy và chạy được.

```sql
SELECT table_name,column_name,data_type,numeric_precision,numeric_scale
FROM information_schema.columns WHERE table_schema='public'
 AND table_name IN ('stock_daily','index_daily') AND data_type='numeric'
ORDER BY table_name,ordinal_position;
SELECT p.proname,p.prosecdef,p.provolatile,p.proconfig,
 has_function_privilege('anon',p.oid,'EXECUTE') AS anon_execute,
 has_function_privilege('authenticated',p.oid,'EXECUTE') AS authenticated_execute,
 has_function_privilege('service_role',p.oid,'EXECUTE') AS service_execute
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='public' AND p.proname IN
 ('persist_stock_daily_validation_v1','persist_daily_raw_numeric_v1',
  'persist_stock_daily_numeric_v1','persist_index_daily_numeric_v1','read_daily_numeric_scope_v1');
SELECT t,has_table_privilege('service_role','public.'||t,'SELECT,INSERT,UPDATE') AS clean_log_access
FROM unnest(ARRAY['stock_daily','index_daily','stock_data_quality_logs']) t;
SELECT t,has_table_privilege('service_role','public.'||t,'SELECT,INSERT') AS raw_access
FROM unnest(ARRAY['stock_raw_daily','index_raw_daily']) t;
SELECT pg_get_functiondef('public.persist_stock_daily_validation_v1(text,date,text,jsonb,jsonb)'::regprocedure);
```

Kỳ vọng prosecdef=false, service execute=true, anon/authenticated=false; read RPC volatility s. Giữ yêu cầu schema USAGE và sequence log USAGE. Không tự mở rộng table grant/RLS.

SQL kiểm tra tiền đúng scope:

```sql
SELECT r.symbol,r.trading_date,r.source,r.data_hash,r.payload->>'totalMatchValue' AS raw_value,
 c.total_match_val::text AS clean_value,c.validation_status
FROM public.stock_raw_daily r LEFT JOIN public.stock_daily c USING(symbol,trading_date)
WHERE r.source='ssi_v3' AND r.symbol IN ('BID','TCB','VCB') AND r.trading_date=DATE '2025-03-12'
ORDER BY r.symbol,r.data_hash;
SELECT r.index_code,r.trading_date,r.source,r.payload->>'netPurchasesForeignValue' AS raw_value,
 c.net_foreign_purchase_value::text AS clean_value
FROM public.index_raw_daily r LEFT JOIN public.index_daily c
 ON upper(c.index_code)=upper(r.index_code) AND c.trading_date=r.trading_date
WHERE upper(r.index_code)='VNINDEX' AND r.source='SSI_v3_indexSummary'
 AND r.trading_date=DATE '2026-03-17';
SELECT symbol,trading_date,status,issue_count,details->>'policy_version' AS policy,
 details->'issues' AS issues,details->'history' AS history
FROM public.stock_data_quality_logs WHERE check_name='stock_daily_validation_v1'
 AND symbol IN ('BID','TCB','VCB') AND trading_date=DATE '2025-03-12';
```

Tính lại số RAW/version/key phần lẻ trong range tường minh trước rerun (ví dụ đúng một ngày; owner chủ động đổi cả hai đầu):

```sql
WITH parsed AS (
 SELECT r.*,CASE WHEN (r.payload->>'totalMatchValue') ~ '^[+-]?[0-9]+([.][0-9]+)?([eE][+-]?[0-9]+)?$'
 THEN (r.payload->>'totalMatchValue')::numeric END AS value
 FROM public.stock_raw_daily r WHERE r.source='ssi_v3'
 AND r.symbol IN ('BID','TCB','VCB')
 AND r.trading_date BETWEEN DATE '2025-03-12' AND DATE '2025-03-12'
), fractional AS (SELECT * FROM parsed WHERE value>=0 AND value<>trunc(value))
SELECT count(*) AS fractional_raw_versions,
 count(DISTINCT(f.symbol,f.trading_date)) AS fractional_keys,
 count(DISTINCT(f.symbol,f.trading_date)) FILTER(WHERE c.symbol IS NULL) AS raw_only_keys
FROM fractional f LEFT JOIN public.stock_daily c USING(symbol,trading_date);
```

Rollback: pause writer, deploy app trước có chủ đích, giữ function additive/RAW/log. V1 cập nhật vẫn nhận policy 1.0.0/JSONB nên rollback app không cần drop hàm hoặc phục hồi integer-money bug. App cũ không có guarantee exact mới. Cleanup/restore function chỉ sau review riêng khi mọi caller đã dừng. Không xóa evidence/relabel status để ép pass; rollback migration không undo dữ liệu ingest sau đó.

## WRITE đúng scope — chỉ owner, chưa chạy

Sau migration/deploy/audit review, theo rule active-scope/ngày hợp lệ hiện có:

```bash
python main.py stock-eod-backfill --from 12/03/2025 --to 12/03/2025 --symbols BID --data-source ssi_v3
# Chỉ nếu exact audit chứng minh cần rerun Index:
python main.py index-eod-backfill --from 17/03/2026 --to 17/03/2026 --indexes VNINDEX --data-source ssi_v3
```

Lệnh gọi SSI và ghi source data. Với Index backfill, phải đọc status/errors trong per-day/per-index summary; top-level error_count hiện có không thay thế chẩn đoán record-level. Task chưa chạy production rerun. Không tự mở rộng theo số đếm lịch sử, force downgrade VALID hoặc tự chạy features/signals/backtests. Features hiện tại không tự loại PARTIAL; consumer phải xử lý status/NULL. Sửa source có thể thay đổi input của một lần tính feature được cho phép riêng sau này.

## Kiểm chứng và giới hạn

Lệnh chính xác và inventory file ở cuối. PostgreSQL 17 được tải/extract trong /tmp, tạo cluster test riêng bind 127.0.0.1:55432; không thêm system package hoặc dependency repo. Test từ chối TEST_DATABASE_URL production. CI hiện có PostgreSQL 16 để kiểm chứng độc lập.

Code/test không đồng nghĩa production đã được sửa. Migration production pending; lịch sử pending owner revalidation/backfill đúng scope; SSI precision/completeness độc lập còn cần source verification. Không SSI live, production migration/backfill/features write. Đã đọc catalog và bảy mẫu numeric đúng scope qua Supabase connector.

## Lệnh đã chạy và kết quả

URL dưới đây chỉ là cluster test local của workspace, không phải URL production.

```bash
source .venv/bin/activate
export TEST_DATABASE_URL=postgresql://agent@127.0.0.1:55432/postgres
python -m pytest -q tests/data_contracts tests/validation/test_daily_validator.py tests/validation/test_stock_daily_v1.py tests/validation/test_stock_daily_v1_postgres.py tests/validation/test_daily_numeric_postgres.py tests/validation/test_daily_numeric_diagnostics.py tests/database/test_daily_numeric_transport.py tests/database/test_stock_daily_quality_rpc.py tests/ingest/test_index_daily_pipeline.py tests/data_sources/test_ssi_v3_stock_daily.py tests/data_preview/test_v3_client.py tests/inspectors/test_ssi_api_mapping.py tests/test_app_controlled_timestamps.py tests/pipeline/test_backfill_pipeline.py tests/pipeline/test_stock_eod_pipeline.py
python -m pytest -q
python -m compileall -q main.py src scripts tests
python main.py --help
python main.py daily-numeric-quality --help
python main.py stock-eod-quality --help
python main.py stock-eod --help
python main.py stock-eod-backfill --help
python main.py index-eod --help
python main.py index-eod-backfill --help
python main.py index-preview --help
git diff --check
git diff --exit-code 7eb92be8a67c543a33865b7d3f1d044b4473beed -- migrations/20261103_stock_daily_quality_v1.sql
```

**Focused: 235 passed; full: 1.391 passed; 0 failed/0 skipped** trên PostgreSQL 17 local, gồm 34 test migration/RPC daily và 8 test encoder SDK thật qua HTTP mock. Compile/8 CLI help/diff checks đều pass; migration V1 cũ không đổi. Repo không có cấu hình linter; đã kiểm syntax/whitespace. CI PostgreSQL 16 được ghi riêng trong PR sau push.

## Danh sách file

### Đã sửa

- `README.md`
- `README.vi.md`
- `docs/CLI_REFERENCE.md`
- `docs/CLI_REFERENCE.vi.md`
- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/DATA_PIPELINE.md`
- `docs/README.md`
- `docs/README.vi.md`
- `docs/SSI_DAILY_INDEX_MAPPING.md`
- `docs/STOCK_DAILY_QUALITY_V1.md`
- `docs/STOCK_DAILY_QUALITY_V1.vi.md`
- `docs/STOCK_EOD_PIPELINE.md`
- `docs/STOCK_EOD_PIPELINE.vi.md`
- `docs/backfill/README.md`
- `docs/backfill/README.vi.md`
- `migrations/README.md`
- `migrations/README.vi.md`
- `scripts/inspectors/ssi_rest/README.md`
- `scripts/inspectors/ssi_rest/README.vi.md`
- `scripts/inspectors/ssi_rest/client.py`
- `scripts/inspectors/ssi_rest/inspect.py`
- `src/cli/README.md`
- `src/cli/README.vi.md`
- `src/cli/__init__.py`
- `src/cli/parser.py`
- `src/contracts/README.md`
- `src/contracts/README.vi.md`
- `src/contracts/definitions.json`
- `src/contracts/derived.py`
- `src/contracts/engine.py`
- `src/contracts/mappings/ssi_v3.json`
- `src/contracts/transforms.py`
- `src/database/README.md`
- `src/database/README.vi.md`
- `src/database/client.py`
- `src/ingest/index_daily/README.md`
- `src/ingest/index_daily/README.vi.md`
- `src/ingest/index_daily/index_daily_mapper.py`
- `src/ingest/index_daily/index_daily_persistence.py`
- `src/ingest/index_daily/index_daily_preview.py`
- `src/ingest/index_daily/index_daily_service.py`
- `src/ingest/stock_daily/README.md`
- `src/ingest/stock_daily/README.vi.md`
- `src/ingest/stock_daily/daily_mapper.py`
- `src/ingest/stock_daily/daily_service.py`
- `src/providers/ssi/adapters/v3.py`
- `src/providers/ssi/clients/rest_v3.py`
- `src/quality/README.md`
- `src/quality/README.vi.md`
- `src/quality/stock_daily_diagnostics.py`
- `src/quality/validators/README.md`
- `src/quality/validators/README.vi.md`
- `src/quality/validators/daily_validator.py`
- `src/quality/validators/index_daily_validator.py`
- `src/quality/validators/stock_daily_v1.py`
- `tests/data_contracts/test_engine.py`
- `tests/data_preview/test_intraday_preview.py`
- `tests/data_preview/test_v3_client.py`
- `tests/database/test_stock_daily_quality_rpc.py`
- `tests/ingest/test_index_daily_pipeline.py`
- `tests/ingest/test_provider_boundary.py`
- `tests/inspectors/test_ssi_api_mapping.py`
- `tests/test_app_controlled_timestamps.py`
- `tests/validation/test_stock_daily_v1.py`
- `tests/validation/test_stock_daily_v1_postgres.py`

### Tạo mới

- `docs/DAILY_NUMERIC_PRECISION.md`
- `docs/DAILY_NUMERIC_PRECISION.vi.md`
- `docs/SSI_DAILY_INDEX_MAPPING.vi.md`
- `migrations/20261104_daily_numeric_precision.sql`
- `src/cli/quality.py`
- `src/contracts/numeric.py`
- `src/quality/daily_numeric_diagnostics.py`
- `src/quality/validators/index_daily_numeric.py`
- `tests/data_contracts/test_daily_exact_numeric.py`
- `tests/database/test_daily_numeric_transport.py`
- `tests/validation/test_daily_numeric_diagnostics.py`
- `tests/validation/test_daily_numeric_postgres.py`

Không xóa file. Fixture HTTP dùng chung chỉ được bổ sung bytes cho kiểm tra daily; thuật toán intraday không đổi.
