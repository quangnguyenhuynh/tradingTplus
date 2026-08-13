# Trading T+ - Spec Historical Analog Phase 1

Trạng thái: **hợp đồng đã chốt; nền backend EOD V1 đã triển khai**

Ngày rà soát: **2026-08-06**

Thay thế: hướng strategy/rule cố định và approve rule trong thư mục này.

## 1. Câu hỏi sản phẩm

Tại mỗi checkpoint, Phase 1 chỉ trả lời một câu hỏi:

> Với trạng thái an toàn thời điểm của SSI hiện tại, chính SSI đã diễn biến thế
> nào sau những lần SSI có trạng thái lịch sử tương tự ở cùng checkpoint?

```text
trạng thái SSI an toàn thời điểm lúc 13:30
  -> profile matching đã version
  -> các trạng thái SSI lịch sử tương tự lúc 13:30
  -> phân phối outcome H+1 / H+3 / H+5 (và H+10 trong EOD V2)
  -> phân tích chỉ-đọc kèm evidence và độ bất định
```

Phase 1 không bắt đầu bằng rule mua/bán và không approve một strategy giao dịch
cố định. Đối tượng được kiểm định và approve là **phương pháp historical
analog**: bộ feature, transform/bucket, matching, data-quality gate, entry/outcome
model, thống kê và tiêu chí validation.

## 2. Nguyên tắc bắt buộc: chỉ cùng mã

- Trạng thái SSI hiện tại chỉ so với lịch sử SSI.
- Trạng thái HPG hiện tại chỉ so với lịch sử HPG.
- Candidate lịch sử phải ở cùng checkpoint với trạng thái hiện tại.
- Không được thêm HPG, FPT hoặc mã khác vào tập mẫu của SSI.
- Nếu SSI không đủ quan sát tương tự hợp lệ thì trả `insufficient_sample`; không
  được nới phạm vi sau khi thấy outcome chỉ để làm số mẫu đẹp hơn.

`Group` hoặc `group_key` chỉ là mô tả deterministic của trạng thái feature tương
tự trên một mã, không phải nhóm nhiều cổ phiếu. Mô hình cross-sectional hoặc gom
nhiều mã trong tương lai phải là phương pháp, version, báo cáo validation và kết
quả hiển thị riêng; không thuộc spec này.

## 3. Code hiện tại và đích mới

Runtime, CLI, schema snapshot, spec và test của hướng rule cũ đã bị xóa trong
cleanup 10/08/2026. Hai migration tạo/enforce cũ chỉ còn là deployment history;
cleanup migration sau đó xóa các bảng đã retire khi được apply thủ công.

Nền Historical Analog EOD V1 đã triển khai profile có version, snapshot/outcome,
chronological validation, review, query evidence, repository/service boundary và
parser CLI `analogs`. Distance threshold null và profile draft hiện chặn final
approval/query production. Các checkpoint intraday nằm ngoài scope EOD V1 đã
triển khai.

## 4. Phạm vi

Phase 1 gồm:

- snapshot an toàn thời điểm tại 09:30, 11:30, 13:30 và 14:30;
- matching lịch sử cùng mã/cùng checkpoint;
- outcome/risk theo horizon đã cấu hình (EOD V1 H+1/H+3/H+5; EOD V2 thêm H+10);
- validation ngoài mẫu theo thời gian;
- approve phương pháp có version;
- phân tích hiện tại chỉ-đọc và audit record tùy chọn.

Phase 1 chưa gồm:

- signal mua/bán, cảnh báo, xếp hạng hoặc cooldown;
- quản trị danh mục, %NAV, tương quan hoặc giới hạn vị thế;
- đặt lệnh, kết nối broker hoặc chi phí ngoài cost model nghiên cứu đã version;
- AI/ML tự chọn feature hoặc tự động dò tham số;
- gom mẫu nhiều mã;
- tự chạy sau ingest hoặc feature.

## 5. Nguồn dữ liệu và provenance

| Nguồn | Vai trò |
| --- | --- |
| `features`, timeframe `1d` | Xu hướng, động lượng và thanh khoản của phiên hoàn tất trước đó. |
| `features`, timeframe `15m`/`60m` | Trạng thái intraday đã đóng và sẵn sàng tại checkpoint. |
| `stock_intraday`, timeframe `1m` | Entry giả định và kiểm tra availability sau checkpoint. |
| `stock_daily` | Trục phiên quan sát và outcome close/high/low H+. |
| Evidence completeness/validation | Loại symbol-session-timeframe không đủ điều kiện. |

Hợp đồng Phase 0 tiếp tục là nguồn chuẩn:

- feature `1d` chỉ lấy từ `stock_daily`;
- feature `15m`/`60m` aggregate từ clean 1m `stock_intraday`;
- không đổi missing thành 0;
- không tạo row giả cho cuối tuần, ngày nghỉ, API rỗng hoặc endpoint không hỗ trợ;
- pipeline analog tách khỏi ingest và feature.

Bối cảnh thị trường/ngành có thể trở thành dimension khi nguồn và availability
đúng thời điểm đã được kiểm chứng. Dù vậy, tập outcome lịch sử cho SSI vẫn chỉ
chứa quan sát SSI.

## 6. Hợp đồng thời gian và chống look-ahead

- Hiểu checkpoint theo `Asia/Ho_Chi_Minh`; timestamp lưu phải timezone-aware.
- Phiên hiện tại `E` chỉ dùng feature daily của phiên hoàn tất gần nhất trước
  `E`, thường là `D`.
- Feature intraday chỉ hợp lệ khi nến đã đóng và
  `available_at <= checkpoint_time`.
- `features.time` hiện là bucket start, không chứng minh nến đã sẵn sàng.
- Row 15m bắt đầu 09:30 chưa dùng được lúc 09:30, chỉ dùng từ 09:45. Row 60m bắt
  đầu 09:00 chưa dùng được lúc 09:30.
- Phải xử lý rõ biên phiên và nghỉ trưa; không aggregate xuyên ngày hoặc xuyên
  nghỉ trưa.
- Mỗi dimension bắt buộc có freshness limit. Thiếu hoặc stale thì trả
  `not_evaluable`, không tự lấy một row cũ tùy ý.

Mỗi snapshot phải giữ đủ lineage để tái lập quyết định:

- symbol, phiên, checkpoint và decision time;
- timeframe feature, bucket start, `available_at` và giá trị đã dùng;
- profile code/version/hash;
- data-quality và exclusion reason;
- data/version identity hoặc source fingerprint tương đương.

## 7. Snapshot và matching profile

Một snapshot logic gồm:

```json
{
  "symbol": "SSI",
  "session": "2026-08-06",
  "checkpoint": "13:30",
  "decision_time": "2026-08-06T13:30:00+07:00",
  "profile": {"code": "TPLUS_ANALOG_CORE", "version": 1, "hash": "..."},
  "status": "evaluable",
  "feature_values": {},
  "bucket_labels": {},
  "group_key": "...",
  "input_refs": [],
  "data_quality": {}
}
```

Trạng thái tối thiểu:

| Status | Ý nghĩa |
| --- | --- |
| `evaluable` | Đủ input an toàn thời điểm và vượt data-quality gate. |
| `not_evaluable` | Input bắt buộc thiếu/stale/incomplete hoặc không có entry hợp lệ. |
| `excluded` | Symbol-session không đạt eligibility/completeness đã version. |
| `insufficient_sample` | Snapshot hiện tại hợp lệ nhưng tập match cùng mã quá ít hoặc không đáng tin. |

Profile bất biến theo `profile_code + version + config_hash` và khai báo:

- checkpoint hỗ trợ;
- dimension bắt buộc/tùy chọn và timeframe nguồn;
- transform và bucket fixed/categorical hoặc quantile chỉ học trong training;
- missing/freshness rule;
- matching/fallback level định trước;
- minimum raw/effective sample riêng từng mã;
- entry, cost, outcome và holding-horizon model;
- chronological split và acceptance criteria.

Boundary không được tự đổi theo snapshot hiện tại hoặc future outcome. Fallback
chỉ được bỏ dimension đã khai báo trước. Nếu mọi level đều không đủ mẫu, trả
`insufficient_sample`.

## 8. Build lịch sử và outcome

Với từng `symbol + session + checkpoint` đủ điều kiện:

1. Resolve observed trading sessions theo calendar contract đã version.
2. Áp completeness/eligibility trước khi tạo snapshot.
3. Dùng trạng thái daily của phiên hoàn tất trước đó.
4. Chỉ dùng feature intraday fresh và đã đóng tại checkpoint.
5. Tạo bucket label và group key deterministic.
6. Resolve entry theo convention cố định, có version.
7. Tính đúng horizon của profile theo observed trading sessions (EOD V1 H+1/H+3/H+5; EOD V2 thêm H+10).
8. Giữ missing/exclusion reason thay vì fill dữ liệu.

Entry model đề xuất ban đầu là `next_tradable_1m_open_v1`: open của nến clean 1m
hợp lệ đầu tiên có thời gian lớn hơn decision time trong cùng phiên. Thiếu entry
thì loại khỏi denominator và báo rõ.

Với H+N, gross return = `close_HN / entry_price - 1`; net return áp fee, tax và
slippage assumptions đã version. MFE/MAE, target-before-stop hoặc path metric
khác chỉ tính từ quan sát hợp lệ trong đúng holding window.

Build sau này phải hỗ trợ full history, incremental và scoped replace chính xác.
Write phải idempotent hoặc immutable theo data/profile identity; không được giữ
child outcome cũ sau rebuild.

## 9. Thống kê và baseline

Với mỗi `symbol + profile + checkpoint + group + matching level + horizon`, tối
thiểu trả:

- raw/usable sample, missing count, số phiên riêng biệt và effective sample;
- xác suất net return dương;
- xác suất target/loss đã version;
- mean, median và quantile liên quan;
- downside risk và MFE/MAE khi đủ điều kiện;
- khoảng tin cậy, ban đầu dùng Wilson cho xác suất nhị phân;
- unconditional baseline cùng mã, cùng checkpoint trong kỳ so sánh hợp lệ;
- lift/chênh lệch so với baseline;
- kỳ training/validation/test và profile/data identity.

Không hiển thị xác suất nếu thiếu số mẫu và độ bất định. Baseline cũng riêng từng
mã: evidence analog SSI so với baseline SSI, không so với pool toàn thị trường.

## 10. Validation và approval

Không random split time series. Dùng training, validation và final test theo thứ
tự thời gian; thêm walk-forward khi phù hợp. Quantile bucket chỉ fit trên
training rồi đóng băng. Evidence cho một historical prediction chỉ được dùng các
record hợp lệ đứng trước nó.

Evidence bắt buộc:

- test look-ahead tại mọi checkpoint và boundary nến;
- exclusion/completeness reason;
- raw/effective sample theo mã, checkpoint, horizon và giai đoạn;
- calibration, Brier score hoặc probability metric tương đương;
- lift so với baseline cùng mã;
- stability qua thời gian và market regime đã mô tả;
- phân phối return/risk cho mọi horizon cấu hình, gồm H+10 ở EOD V2;
- entry/cost/outcome assumptions và missing count;
- profile hash, data identity và code commit.

Approve/reject exact method identity, không approve trạng thái hiện tại hoặc rule
mua. Đổi dimension, bucket, fallback, checkpoint, freshness, công thức feature,
entry/cost/outcome hoặc acceptance criteria đều phải tăng version và tạo evidence
mới.

## 11. Kết quả runtime

User mở app không làm chạy lại historical validation. Runtime:

1. resolve `symbol + session + checkpoint`;
2. load profile version đã approve;
3. assemble snapshot hiện tại an toàn thời điểm;
4. trả `not_evaluable` nếu input bắt buộc không đạt;
5. chỉ match snapshot trước đó của cùng mã và cùng checkpoint;
6. trả `insufficient_sample` nếu không đạt sample rule định trước;
7. nếu đủ thì trả xác suất, return/risk, sample, confidence interval, baseline
   cùng mã, assumptions và explanation;
8. có thể ghi audit analysis nhưng không ghi signal trong Phase 1.

## 12. Contract triển khai đề xuất

Tên dưới đây là đề xuất; task code phải đối chiếu lại schema và CLI parser:

| Bảng đề xuất | Mục đích |
| --- | --- |
| `analog_profiles` | Metadata/config immutable và lifecycle của phương pháp. |
| `analog_snapshots` | Trạng thái lịch sử/current an toàn thời điểm và lineage. |
| `analog_outcomes` | Entry và outcome H+ của snapshot. |
| `analog_validation_runs` | Evidence/metrics validation theo thời gian. |
| `analog_group_stats` | Thống kê group cùng mã theo checkpoint/horizon. |
| `analog_profile_reviews` | Quyết định approve/reject có audit. |
| `analog_queries` | Audit phân tích runtime tùy chọn; không phải signal. |

CLI minh họa, hiện chưa tồn tại:

```bash
python main.py analogs history build --profile TPLUS_ANALOG_CORE --version 1 --from 01/01/2021 --to 31/07/2026 --symbols SSI
python main.py analogs validate --profile TPLUS_ANALOG_CORE --version 1 --symbols SSI
python main.py analogs query --profile TPLUS_ANALOG_CORE --version 1 --symbol SSI --date 06/08/2026 --checkpoint 13:30
```

Không command nào được tự gọi ingest, feature, signal, alert hoặc portfolio logic.

## 13. Test và acceptance khi triển khai

Chưa được xem là hoàn thành nếu test chưa chứng minh:

- availability đúng tại 09:30/09:45, 11:30, 13:30 và 14:30;
- daily input từ phiên trước và không leak daily của phiên hiện tại;
- matching tuyệt đối cùng mã và cùng checkpoint;
- outcome mã khác không thể lọt vào sample hoặc baseline;
- profile hash, bucket, group key và fallback order deterministic;
- thiếu/stale input trả `not_evaluable`;
- thiếu mẫu trả `insufficient_sample` và không trả probability;
- mapping H+ qua cuối tuần/ngày nghỉ dùng observed-session rule;
- denominator, confidence interval, baseline và lift đúng;
- full/incremental/scoped-replace không giữ outcome cũ;
- runtime không tạo signal, alert hoặc gợi ý %NAV.

Chạy targeted test trước, sau đó full offline suite, compileall và CLI help.
Smoke SSI/Supabase mặc định read-only nếu chưa approve exact write scope.

## 14. Thứ tự triển khai

1. Snapshot time-safe và leakage test.
2. Profile immutable, snapshot cùng mã, outcome và build modes.
3. Validation OOS theo thời gian và approve profile.
4. Runtime lookup read-only và audit record tùy chọn.

Mỗi mục nên là một task/PR riêng. Thay đổi schema bắt buộc có migration.

## 15. Ảnh hưởng database của task tài liệu

- Migration: none.
- Database row: none.
- Backfill market data/feature: none.
- Task triển khai sau phải có schema/migration được review riêng và historical
  build có scope cho analog snapshot/outcome.

### Boundary runtime V1 đã triển khai (chỉ EOD)

Runtime V1 hiện persist snapshot EOD từ `features.timeframe='1d'` và outcome H+1/H+3/H+5 theo observed session từ `stock_daily`. Query production đọc evidence đã persist; ghi audit chỉ được phép khi exact profile đã approved và có threshold số đã freeze. Profile source hiện vẫn draft/threshold null. Lệnh inspect là đường research/debug read-only, tính trong memory với threshold tạm thời explicit. Checkpoint intraday, signal, ranking, alert, sizing danh mục và rule backtest không thuộc runtime V1 này.

EOD V2 là identity profile bất biến riêng, giữ chín dimension và dùng
H+1/H+3/H+5/H+10. H+10 là phiên `stock_daily` quan sát thứ mười sau D. V2 cần
history/validation riêng; không tái sử dụng hoặc sửa row V1. V2 vẫn draft và
threshold null nên production tiếp tục bị chặn.
