# Tài liệu dự án

Tài liệu cấp repository về sản phẩm, kiến trúc, trạng thái, CLI và database.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Tài liệu chính

| File | Mục đích |
| --- | --- |
| `PROJECT_OVERVIEW.md` | Mục tiêu sản phẩm, ưu tiên Phase 0, use case và tổng quan component. |
| `CURRENT_STATE.md` | Đánh giá trạng thái code tại một thời điểm và các khoảng thiếu. |
| `ARCHITECTURE_DECISIONS.md` | Quyết định pipeline và hợp đồng dữ liệu đã chốt. |
| `CLI_USAGE.md` | Hướng dẫn command production và vận hành. |

Ghi chú database bổ sung hiện nằm ở root với tên `docs_db_schema.md`.

## Quy tắc tài liệu

- Phân biệt rõ hành vi code hiện tại và phương án tương lai.
- Đối chiếu nội dung với code, schema, migration và test.
- Tài liệu trạng thái theo thời điểm phải ghi ngày rà soát.
- Không mô tả signal/backtest research hoặc MVP như hành vi production đã kiểm chứng.
- Không kết luận migration đã deploy chỉ vì file có trong repo.

## Lưu ý tài liệu có thể cũ

Một số tài liệu trạng thái có thể cũ sau khi code thay đổi. Ví dụ, code hiện tại tách `daily` và `intraday-ingest`, trong khi một số đoạn trạng thái cũ vẫn gộp hai luồng. Việc cập nhật toàn bộ tài liệu trạng thái nên được thực hiện bằng task riêng sau khi đối chiếu đầy đủ.
