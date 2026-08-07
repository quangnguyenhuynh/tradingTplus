# Task Codex: triển khai framework rule, backtest và approve rule

> **Task lịch sử - không chạy lại.** Kiến trúc trong task này đã bị thay thế bởi
> [`HISTORICAL_ANALOG_SPEC.vi.md`](HISTORICAL_ANALOG_SPEC.vi.md).

Repo: `quangnguyenhuynh/tradingTplus`

Base branch: `dev`

## Mục tiêu

Triển khai framework Phase 1 để thiết kế rule, replay cùng một rule hai bước
trong backtest, và approve đúng một rule/version trước khi rule đó được ghi
signal thật.

Luồng cần có:

```text
rule draft
  -> backtest daily setup + intraday confirmation trên features lịch sử
  -> lưu evidence H+1/H+3/H+5
  -> owner approve một strategy version
  -> chỉ version approved mới được tạo signal thật
```

## Phải đọc trước khi code

Đọc các file sau:

- `AGENTS.md`
- `docs/phase1/RULE_BACKTEST_APPROVAL_SPEC.vi.md`
- `docs/ARCHITECTURE_DECISIONS.md`
- `docs/DATA_CONVENTIONS.md`
- `docs/CURRENT_STATE.md`
- `src/features/README.md`
- `src/features/common.py`
- `src/features/daily.py`
- `src/features/intraday.py`
- `src/features/runtime.py`
- `src/database/client.py`
- `migrations/20260731_drop_legacy_signal_backtest.sql`
- các test liên quan trong `tests/features/`, `tests/cli/`, `tests/validation/`

Sau đó báo đủ 10 mục trước khi code theo `AGENTS.md`.

## Scope

Chỉ thêm code mới. Không khôi phục signal/backtest legacy.

Tạo:

```text
src/strategies/
src/signals/
src/backtest/
tests/strategies/
tests/signals/
tests/backtest/
```

Mỗi folder/package mới trong `src` và `tests` phải có `README.md` và
`README.vi.md`.

## Yêu cầu chính

### Strategy framework

- Tạo interface chung ở `src/strategies/base.py`.
- Tạo registry ở `src/strategies/registry.py`.
- Tạo ít nhất hai strategy draft:
  - `BREAKOUT_V1`
  - `PULLBACK_V1`
- Mỗi strategy phải có:
  - `strategy_code` ổn định;
  - `version` dạng số nguyên;
  - config bất biến;
  - `daily_setup(...)`;
  - `intraday_confirm(...)`;
  - khai báo timeframe intraday bắt buộc theo từng mốc scan.
- Evaluator trả decision có cấu trúc:
  - `passed`;
  - `status`: ví dụ `passed`, `failed`, `not_evaluable`;
  - `reasons`;
  - `metrics`;
  - feature keys đã dùng.

### Signal framework

- `src/signals/daily_setup.py`: tạo setup candidate từ `features` timeframe `1d`.
- `src/signals/scanner.py`: confirm candidate tại mốc scan bằng feature `15m`/`60m`
  đã đóng nến.
- `src/signals/writer.py`: ghi dữ liệu idempotent.
- Scan signal thật phải từ chối strategy chưa `approved`.
- Daily setup chưa phải signal. Chỉ intraday confirmation đạt mới có signal.

### Backtest framework

- `src/backtest/replay.py`: replay cùng strategy evaluator trên lịch sử:
  - daily setup ở phiên `D`;
  - intraday confirmation ở phiên giao dịch kế tiếp `E`;
  - chỉ tạo simulated signal khi đạt cả hai bước.
- `src/backtest/execution.py`:
  - entry estimate dùng nến clean `stock_intraday` 1m giao dịch được đầu tiên
    sau decision time;
  - mặc định lấy `open` của nến 1m đó;
  - thiếu entry phải lưu rõ.
- `src/backtest/outcome.py`:
  - outcome dùng `stock_daily.close_price` tại close H+1, H+3, H+5 sau phiên entry;
  - thiếu outcome phải lưu rõ.
- `src/backtest/metrics.py`: tính sample size, gross/net return, win-rate,
  average/median return, downside tail và missing counts.
- `src/backtest/approval.py`: chỉ chuyển strategy version sang `approved` khi
  có backtest evidence và review decision rõ ràng.

### Database

Tạo một migration additive theo naming style date-prefixed hiện có. Không sửa
raw, clean hoặc bảng `features`.

Bảng active dự kiến:

- `strategies`
- `strategy_setups`
- `signals`
- `backtest_runs`
- `backtest_signals`
- `strategy_reviews`

Mọi write path cần unique/idempotency key. Migration phải có verification SQL và
rollback guidance. Không tạo lại `trading_signals` hoặc `backtest_data`.

### CLI

Thêm command explicit, không đổi hành vi CLI hiện tại:

- `python main.py strategies list`
- `python main.py strategies backtest ...`
- `python main.py strategies approve ...`
- `python main.py signals daily-setup ...`
- `python main.py signals scan ...`

Signal/backtest không được tự chạy từ ingest, EOD hoặc feature commands.

## Ràng buộc

- Rule đọc chính từ `features`.
- `stock_intraday` chỉ dùng cho ước tính entry/execution.
- `stock_daily` dùng cho outcome theo phiên nắm giữ.
- H+1/H+3/H+5 tính theo phiên giao dịch, không theo ngày lịch.
- Không dùng feature tương lai.
- Intraday chỉ dùng feature đã đóng nến và available tại mốc scan.
- Không thêm AI, probability, NAV, cooldown alert, foreign trading hoặc orderbook
  trong task này.
- Không tối ưu threshold để làm đẹp lợi nhuận trong task này. Rule ví dụ phải
  minh bạch và test được.
- Test không ghi production data.

## Acceptance criteria

- Strategy draft đăng ký và evaluate offline được.
- Backtest dùng cùng evaluator hai bước với signal scan.
- Kết quả daily-only không được approve strategy tạo signal intraday thật.
- Strategy chưa approved không ghi được live signal.
- Rerun daily setup, signal scan và backtest không sinh trùng.
- Outcome H+1/H+3/H+5 dựa trên phiên giao dịch và close price.
- Entry/outcome thiếu được giữ trạng thái missing, không fill.
- Migration additive và có verification SQL.
- README.md và README.vi.md tồn tại cho folder source/test mới.

## Test cần chạy

Thêm unit test cho:

- strategy registry;
- daily setup pass/fail/not-evaluable;
- intraday confirmation pass/fail/not-evaluable;
- không ghi signal từ strategy chưa approved;
- không duplicate setup/signal khi rerun;
- backtest replay chạy đủ daily và intraday;
- mapping outcome H+1/H+3/H+5 theo phiên;
- thiếu entry và thiếu outcome;
- migration text có đủ bảng, unique key, verification SQL và không tạo lại bảng
  legacy.

Chạy:

```bash
python -m pytest -q tests/strategies tests/signals tests/backtest
python -m pytest -q tests/features tests/cli
python -m compileall main.py src scripts tests
python main.py --help
```

Nếu thiếu credential thì không chạy smoke test SSI/Supabase live; báo rõ là chưa
chạy.

## Final report bắt buộc

Báo:

- đã sửa gì;
- file nào thay đổi;
- migration/database impact;
- có cần backfill không;
- lệnh test đã chạy;
- kết quả test;
- rủi ro còn lại;
- bước tiếp theo.
