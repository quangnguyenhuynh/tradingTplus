# GitHub Actions workflows

Automation cho test và các pipeline Trading T+ chạy tường minh.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Workflow hiện tại

| File | Trigger | Command hiện tại |
| --- | --- | --- |
| `tests.yml` | Pull request và push vào `dev` | `python -m pytest -q` trên Python 3.11, có service PostgreSQL 16 và `TEST_DATABASE_URL`. |
| `eod.yml` | Thứ Hai–Thứ Sáu lúc 09:30 UTC (16:30 Việt Nam) và manual | `python main.py eod [date]`. |
| `index-eod.yml` | Thứ Hai–Thứ Sáu lúc 09:45 UTC (16:45 Việt Nam) và manual | `python main.py index-daily [date] [--indexes ...]`. |
| `features.yml` | Chỉ manual | `python main.py features ...` với input rõ ràng. |

## Lưu ý vận hành

- `eod.yml` chạy stock daily ingest, stock intraday ingest, index daily ingest và completeness validation. Scope bỏ trống chỉ dùng các dòng `status = 'active'` trong `symbols` và `index_master`; workflow không tính feature.
- `index-eod.yml` chỉ chạy SSI DailyIndex raw/clean ingest qua `index-daily`. Input index rỗng dùng các dòng active trong `index_master`; index explicit có thể retry hoặc catch up dữ liệu nguồn mà không chạy stock ingest, completeness, feature, signal, backtest hoặc Analog.
- Workflow schedule chạy theo ngày trong tuần; ngày nghỉ sàn hoặc SSI trả rỗng vẫn hiện rõ trong summary command và không tạo dữ liệu giả.
- `features.yml` tách khỏi ingest và cho phép chọn mode/date/symbol/timeframe.
- Credential SSI/Supabase lấy từ repository secrets.
- Test PostgreSQL atomic replace thuộc main suite và không được skip vì
  `tests.yml` luôn cấp test database.
- Parity lịch sử dài và mọi module regression pagination được collect bởi cùng
  command `python -m pytest -q` không filter trên pull request và push `dev`.
- Không tự động nối signal hoặc backtest vào workflow ingest nếu chưa có task kiến trúc rõ ràng.

## Kiểm tra

Rà soát YAML, chạy command tương ứng ở local và dùng `tests.yml` để kiểm tra offline trước khi merge.
