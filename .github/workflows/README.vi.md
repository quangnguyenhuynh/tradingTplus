# GitHub Actions workflows

Automation cho test và các pipeline Trading T+ chạy tường minh.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Workflow hiện tại

| File | Trigger | Command hiện tại |
| --- | --- | --- |
| `tests.yml` | Pull request và push vào `dev` | `python -m pytest -q` trên Python 3.11, có service PostgreSQL 16 và `TEST_DATABASE_URL`. |
| `stock-eod.yml` | Thứ Hai–Thứ Sáu 16:30 Asia/Ho_Chi_Minh + manual | Resolve ngày lịch theo giờ Việt Nam rồi chạy daily-only `python main.py stock-eod <date>`. |
| `stock-intraday.yml` | Thứ Hai–Thứ Sáu 17:00 Asia/Ho_Chi_Minh + manual | 1m-only `python main.py stock-intraday <date>`. |
| `index-eod.yml` | Thứ Ba–Thứ Bảy 08:30 Asia/Ho_Chi_Minh + manual | Lịch tự động gọi `python main.py index-daily <ngày trước slot dự kiến theo giờ Việt Nam> [--indexes ...]`; manual dùng ngày truyền vào nếu có. |
| `features.yml` | Chỉ manual | `python main.py features ...` với input rõ ràng. |

Cả ba workflow ingest khai báo `timezone: "Asia/Ho_Chi_Minh"`. Cron giờ Việt Nam là `30 16 * * 1-5` (Stock EOD), `0 17 * * 1-5` (Stock Intraday) và `30 8 * * 2-6` (Index EOD). Timezone tường minh không đảm bảo runner chạy đúng giờ; vẫn giữ resolver ngày theo slot lịch tập trung.

## Lưu ý vận hành

- `stock-eod.yml` chỉ chạy daily ingest và daily completeness cho `symbols.status = 'active'`. Run theo lịch resolve slot 16:30 Việt Nam gần nhất trong thứ Hai-thứ Sáu rồi truyền tường minh ngày của slot đó, nên runner khởi động trễ qua nửa đêm Việt Nam không làm ngày đích nhảy sang hôm sau. Ngày manual được giữ nguyên; manual không truyền ngày vẫn dùng fallback ngày trong tuần gần nhất tính cả hôm nay theo giờ Việt Nam.
- `stock-intraday.yml` chỉ chạy ingest 1m và intraday completeness khi cả `status` và `intraday_status` là `active`; manual symbols không vượt qua scope này. Run theo lịch resolve slot 17:00 Việt Nam gần nhất từ thứ Hai đến thứ Sáu và truyền ngày tường minh, kể cả khi runner khởi động sau nửa đêm. Ngày manual explicit được ưu tiên; manual không truyền ngày giữ fallback lịch của CLI.
- Hai workflow độc lập với index và không chạy feature/signal/backtest/Analog.
- `index-eod.yml` chỉ chạy SSI DailyIndex raw/clean ingest qua `index-daily`. Lịch tự động chạy lúc 08:30 Việt Nam từ Thứ Ba đến Thứ Bảy, resolve slot dự kiến gần nhất và truyền rõ ngày lịch trước slot đó để lấy dữ liệu tự doanh SSI công bố vào sáng hôm sau. Manual dispatch giữ ngày được truyền tường minh; nếu manual không truyền ngày thì vẫn giữ hành vi lấy ngày lịch trước runtime. Input index rỗng dùng các dòng active trong `index_master`; index explicit có thể retry hoặc catch up dữ liệu nguồn mà không chạy stock ingest, completeness, feature, signal, backtest hoặc Analog.
- Cron GitHub Actions có thể khởi động trễ hơn slot cấu hình. Cả ba workflow đều log event, runtime thực tế theo giờ Việt Nam, slot lịch Việt Nam, ngày đích đã resolve và nguồn scheduled/manual/default; lịch tự động không dùng ngây thơ ngày lịch của runner bị trễ.
- Workflow tự động cố ý dùng ngày lịch hôm trước và không suy diễn lịch nghỉ giao dịch; nếu SSI trả rỗng thì kết quả vẫn hiện rõ trong summary và không tạo dữ liệu giả.
- `features.yml` tách khỏi ingest và cho phép chọn mode/date/symbol/timeframe.
- Credential SSI/Supabase lấy từ repository secrets.
- Test PostgreSQL atomic replace thuộc main suite và không được skip vì
  `tests.yml` luôn cấp test database.
- Parity lịch sử dài và mọi module regression pagination được collect bởi cùng
  command `python -m pytest -q` không filter trên pull request và push `dev`.
- Không tự động nối signal hoặc backtest vào workflow ingest nếu chưa có task kiến trúc rõ ràng.

## Kiểm tra

Rà soát YAML, chạy command tương ứng ở local và dùng `tests.yml` để kiểm tra offline trước khi merge.

Ngày theo lịch dùng slot cron `Asia/Ho_Chi_Minh` gần nhất đã qua: Stock EOD 16:30 và Stock Intraday 17:00 lấy ngày phiên đó; Index EOD 08:30 sáng hôm sau lấy ngày lịch trước slot. Quy tắc xử lý stock trễ qua nửa đêm và index trễ trong cùng buổi sáng. Nếu trễ qua một slot lịch tiếp theo, chỉ runtime không thể xác định ngày trigger gốc; hãy truyền ngày manual explicit để chạy bù.
