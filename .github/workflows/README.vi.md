# GitHub Actions workflows

Automation cho test và các pipeline Trading T+ chạy tường minh.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Workflow hiện tại

| File | Trigger | Command hiện tại |
| --- | --- | --- |
| `tests.yml` | Pull request và push vào `dev` | `python -m pytest -q` trên Python 3.11. |
| `eod.yml` | Thứ Hai–Thứ Sáu lúc 09:30 UTC (16:30 Việt Nam) và manual | `python main.py eod [date]`. |
| `features.yml` | Chỉ manual | `python main.py features ...` với input rõ ràng. |

## Lưu ý vận hành

- `eod.yml` chạy daily ingest, intraday ingest và completeness validation; không tính feature.
- `features.yml` tách khỏi ingest và cho phép chọn mode/date/symbol/timeframe.
- Credential SSI/Supabase lấy từ repository secrets.
- Không tự động nối signal hoặc backtest vào workflow ingest nếu chưa có task kiến trúc rõ ràng.

## Kiểm tra

Rà soát YAML, chạy command tương ứng ở local và dùng `tests.yml` để kiểm tra offline trước khi merge.
