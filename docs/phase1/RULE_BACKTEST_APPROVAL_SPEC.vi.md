# Spec thiết kế rule, backtest và approve rule

> **Đã bị thay thế:** Thiết kế fixed-rule này chỉ giữ để audit. Task mới phải
> theo [`HISTORICAL_ANALOG_SPEC.vi.md`](HISTORICAL_ANALOG_SPEC.vi.md). Không
> dùng tài liệu này để approve hoặc vận hành strategy production.

Trạng thái: Tài liệu fixed-rule đã bị thay thế; chỉ giữ để audit.

Ngày rà theo code repo: 2026-08-06.

## Mục tiêu

Spec này chỉ chốt riêng phần:

```text
thiết kế rule
  -> backtest rule
  -> approve rule/version
  -> rule approved mới được ghi signal thật
```

Một rule T+ hợp lệ không chỉ là một bộ lọc daily. Rule dùng để tạo signal thật
phải gồm đủ hai bước:

```text
Bước 1: Daily setup
  -> cuối ngày lọc mã đáng theo dõi cho phiên kế tiếp

Bước 2: Intraday confirmation
  -> phiên kế tiếp, tới mốc giờ cho phép thì kiểm tra xác nhận bằng feature intraday
  -> đạt cả daily và intraday thì mới ghi signal
```

Backtest cũng phải replay đúng hai bước này. Có thể backtest daily-only để tham
khảo, nhưng daily-only không đủ để approve rule dùng cho signal intraday thật.

## Bối cảnh repo hiện tại

- Bảng `features` là input chính của rule.
- Feature production hiện persist `1d`, `15m`, `60m`.
- Feature `1d` tính từ `stock_daily`.
- Feature `15m` và `60m` aggregate từ `stock_intraday` 1m trong feature
  pipeline.
- `stock_intraday` chỉ lưu nến clean `1m`.
- Bảng/code signal và backtest legacy cũ đã bị xoá bằng
  `migrations/20260731_drop_legacy_signal_backtest.sql`.
- PR #121/#123 sau đó thêm lại framework fixed-rule mới. Framework này đang
  đóng băng/đã bị thay thế, không phải contract active của Phase 1.
- Không tạo lại `trading_signals` hoặc `backtest_data` làm contract active.

## Vòng đời rule

| Trạng thái | Ý nghĩa |
| --- | --- |
| `draft` | Rule đã được viết nhưng chưa được phép tạo signal thật. |
| `backtested` | Rule/version đã có kết quả backtest. |
| `approved` | Chủ dự án duyệt rule/version này, được phép chạy signal thật. |
| `retired` | Giữ lại để audit, không tạo signal mới. |

Approve luôn gắn với đúng `strategy_code + version + config_hash`. Nếu sửa điều
kiện, threshold, timeframe, mốc scan, cách tính entry, phí/slippage, feature
formula hoặc bộ dữ liệu đủ điều kiện thì phải tạo evidence mới rồi approve lại.

## Dữ liệu dùng cho rule và backtest

| Dữ liệu | Dùng để làm gì |
| --- | --- |
| `features` `1d` | Lọc daily setup. |
| `features` `15m` / `60m` | Xác nhận intraday tại các mốc giờ. |
| `stock_intraday` `1m` | Ước tính giá vào lệnh sau signal trong backtest. |
| `stock_daily` | Tính kết quả đóng cửa H+1/H+3/H+5. |
| Trading calendar/session | Biết phiên kế tiếp, H+1/H+3/H+5 là phiên nào. |
| Data-quality eligibility | Loại symbol/date/timeframe thiếu hoặc lỗi dữ liệu. |

## Contract của rule hai bước

Mỗi strategy module phải có:

- `strategy_code` ổn định;
- `version` dạng số nguyên;
- config mặc định bất biến;
- daily timeframe bắt buộc: `1d`;
- intraday timeframe bắt buộc theo từng mốc scan;
- `daily_setup(features_1d) -> RuleDecision`;
- `intraday_confirm(setup, intraday_features, scan_slot) -> RuleDecision`.

`RuleDecision` cần có:

- `passed: bool`;
- `reasons: list[str]`;
- `metrics: dict`;
- `input_feature_keys`: symbol, timeframe, time của feature đã dùng.

Live scanner và backtest phải dùng chung evaluator. Không được viết logic rule
riêng trong backtest rồi logic khác trong live scan.

## Luồng scan signal thật

Với mỗi phiên giao dịch `E`:

1. Cuối phiên trước đó `D`, chạy daily setup.
2. Mã đạt daily setup được đưa vào watchlist cho phiên `E`.
3. Tại các mốc scan của phiên `E`, chỉ kiểm tra intraday cho mã đã có setup.
4. Chỉ dùng feature intraday đã đóng nến và available tại hoặc trước mốc scan.
5. Nếu intraday confirmation đạt thì ghi một signal cho đúng rule/version,
   symbol, setup date, scan slot và signal time.

Mốc scan mặc định:

```text
09:30
11:30
13:30
14:30
```

Mỗi strategy phải khai báo mốc nào cần timeframe nào. Nếu thiếu feature bắt buộc
thì kết quả là `not_evaluable`, không được coi là đạt.

## Luồng backtest để approve rule

Với một strategy đang ở `draft`:

1. Chọn giai đoạn lịch sử và universe symbol.
2. Áp data-quality eligibility trước khi chạy rule.
3. Replay daily setup ở cuối mỗi phiên lịch sử `D`.
4. Replay intraday confirmation ở phiên kế tiếp `E` tại các mốc scan cho phép.
5. Chỉ tạo simulated signal khi đạt cả daily setup và intraday confirmation.
6. Ước tính entry bằng nến clean `1m` giao dịch được đầu tiên sau decision time.
   Mặc định lấy `open` của nến 1m kế tiếp, trừ khi execution model được đổi và
   version rõ ràng.
7. Tính outcome bằng `stock_daily.close_price` tại đóng cửa H+1, H+3 và H+5 sau
   phiên entry.
8. Trừ phí, thuế và slippage theo assumption đã version.
9. Lưu metric/evidence để chủ dự án review.

Trong code và docs nên dùng `H+1/H+3/H+5` để chỉ số phiên nắm giữ sau entry,
tránh nhầm với ký hiệu thanh toán T+.

Nếu thiếu giá entry hoặc thiếu giá outcome, phải lưu trạng thái missing và loại
record đó khỏi mẫu tính metric tương ứng. Không fill giá thiếu bằng 0 hoặc dữ
liệu tương lai.

## Gate approve rule

Một rule/version chỉ được chuyển sang `approved` khi có đủ:

- backtest dùng đúng evaluator hai bước daily + intraday;
- báo rõ data-quality filter và số dòng bị loại;
- sample size theo strategy, mốc scan, universe và giai đoạn;
- phân phối return gross/net cho H+1/H+3/H+5;
- phí, thuế, slippage, entry model, exit model đã version;
- win rate, average/median return, downside tail, max adverse excursion hoặc
  proxy drawdown, missing-data count;
- quyết định approve/reject của chủ dự án kèm ghi chú.

Không hardcode một ngưỡng lợi nhuận chung như chân lý. Tiêu chí review nên lưu
theo backtest run hoặc strategy review để sau này đổi có kiểm soát.

## Tổ chức thư mục khi code

```text
src/strategies/
  base.py
  registry.py
  breakout_v1.py
  pullback_v1.py
  README.md
  README.vi.md

src/signals/
  daily_setup.py
  scanner.py
  writer.py
  README.md
  README.vi.md

src/backtest/
  replay.py
  execution.py
  outcome.py
  metrics.py
  approval.py
  README.md
  README.vi.md

tests/strategies/
tests/signals/
tests/backtest/
```

## Bảng tối thiểu dự kiến

Task triển khai code sẽ tạo migration additive. Contract active dự kiến:

| Bảng | Mục đích |
| --- | --- |
| `strategies` | Metadata rule, version, config hash, status và audit fields. |
| `strategy_setups` | Các daily setup cho phiên giao dịch kế tiếp. |
| `signals` | Signal thật/tương lai, chỉ tạo từ strategy đã approved. |
| `backtest_runs` | Scope backtest, assumption, data filter, code/config version và status. |
| `backtest_signals` | Signal mô phỏng lịch sử và outcome H+1/H+3/H+5. |
| `strategy_reviews` | Quyết định approve/reject cho một strategy version dựa trên evidence. |

Mọi write path phải có idempotency key rõ ràng. Rerun cùng setup, scan hoặc
backtest không được sinh trùng dữ liệu.

## Ngoài phạm vi

- AI ranking hoặc probability.
- NAV sizing và portfolio simulation.
- Cooldown/chống spam alert.
- Rule dùng foreign trading hoặc orderbook.
- Sửa hoặc tối ưu feature pipeline.
- Tự động chạy backtest sau feature.
