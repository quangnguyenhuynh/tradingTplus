# Tài liệu dự án

Tài liệu cấp repository về sản phẩm, kiến trúc, trạng thái, CLI và database.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Tài liệu chính

| File | Mục đích |
| --- | --- |
| `PROJECT_OVERVIEW.md` | Mục tiêu sản phẩm, ưu tiên Phase 0, use case và tổng quan component. |
| `CURRENT_STATE.md` | Đánh giá trạng thái code và khoảng thiếu tại một thời điểm; đã rà soát theo code ngày 18/07/2026. |
| `DATA_PIPELINE.md` | Luồng master, daily, intraday, streaming, validation và feature đang chạy. |
| `ARCHITECTURE_DECISIONS.md` | Quyết định pipeline và hợp đồng dữ liệu đã chốt. |
| `CLI_USAGE.md` | Hướng dẫn command production và vận hành. |

Ghi chú database bổ sung hiện nằm ở root với tên `docs_db_schema.md`.

## Quy tắc tài liệu

- Phân biệt rõ hành vi code hiện tại và phương án tương lai.
- Đối chiếu nội dung với code, schema, migration và test.
- Tài liệu trạng thái theo thời điểm phải ghi ngày rà soát.
- Không mô tả signal/backtest research hoặc MVP như hành vi production đã kiểm chứng.
- Không kết luận migration đã deploy chỉ vì file có trong repo.
- Khi tài liệu mâu thuẫn, ưu tiên code thực thi, schema, migration, test và `AGENTS.md` hiện tại.

## Bảo trì

`CURRENT_STATE.md` và `DATA_PIPELINE.md` đã được đồng bộ với việc tách daily/intraday, reuse payload, completeness query, feature contract và streaming-ingest vào ngày 18/07/2026. Cần rà soát lại tài liệu trạng thái mỗi khi hành vi production thay đổi.
