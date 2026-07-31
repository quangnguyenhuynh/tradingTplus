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
| `DATA_CONVENTIONS.md` / `DATA_CONVENTIONS.vi.md` | Quy ước English/Tiếng Việt về timestamp, phiên, missing data, đơn vị và provenance. |
| [`backfill/`](backfill/README.vi.md) | Hành vi, an toàn và command backfill dữ liệu nguồn. |

Hợp đồng database thực thi nằm tại [`../schema.sql`](../schema.sql); lịch sử thay
đổi và SQL triển khai được mô tả trong [`../migrations/`](../migrations/README.vi.md).

## Quy tắc tài liệu

- Phân biệt rõ hành vi code hiện tại và phương án tương lai.
- Đối chiếu nội dung với code, schema, migration và test.
- Tài liệu trạng thái theo thời điểm phải ghi ngày rà soát.
- Không mô tả signal/backtest research hoặc MVP như hành vi production đã kiểm chứng.
- Không kết luận migration đã deploy chỉ vì file có trong repo.
- Khi tài liệu mâu thuẫn, ưu tiên code thực thi, schema, migration, test và `AGENTS.md` hiện tại.

## Bảo trì

Cần rà soát lại tài liệu trạng thái mỗi khi hành vi production thay đổi. Ngày
review ghi trong từng tài liệu là ngày đánh giá, không phải bằng chứng rằng schema
production đã áp dụng toàn bộ migration.
