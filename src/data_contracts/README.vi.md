# Contract dữ liệu chuẩn và mapping theo nguồn

Package này tách ý nghĩa clean data của ứng dụng khỏi hình dạng payload nhà cung cấp. `definitions.json` là từ điển chuẩn cho `stock_daily`, `stock_intraday` 1 phút, `index_daily` và hai danh mục chỉ dành cho inspector là `symbol_list`, `index_list`. Mỗi field khai báo ý nghĩa nghiệp vụ, kiểu, đơn vị, required/NULL, ràng buộc mức field và quy ước ngày/giờ/timeframe liên quan. `stock_daily` dùng contract breaking `2.0.0`, `index_daily` dùng contract breaking `2.0.0`; các dataset còn lại dùng `1.0.0`.

`mappings/ssi_v2.json` chứa mapping có phiên bản riêng; mapping `stock_daily` 2.0.0 dùng contract 2.0.0. File chỉ khai báo alias đã xác nhận, transform trong whitelist, xử lý missing/placeholder đặc thù nguồn và hệ số đổi đơn vị có bằng chứng. Riêng placeholder `0` của giá tham chiếu/trần/sàn daily SSI v2 dùng `ssi_v2_zero_price_to_null`; đây không phải quy tắc chung của contract.

## Xử lý và report

`map_record(source_id, dataset, record, context)` kiểm tra registry/version, chỉ đọc field top-level được khai báo, chuẩn hóa, kiểm tra constraint và trả `MappingResult`. Hàm không tìm đệ quy, đoán tên, gọi API/DB, ghi file hoặc tính feature. Source/dataset/version không biết sẽ lỗi, không fallback.

Report ghi source/dataset/version và số record, đồng thời tách field required/optional bị thiếu, field nguồn chưa dùng, lỗi chuyển kiểu, xung đột alias và vi phạm contract. Count là theo record; danh sách field có thể có nhiều lỗi cho cùng một record bị loại. Service ingest đặt report trong metadata riêng `mapping_report`, không gửi key report xuống bảng clean. Validator nghiệp vụ hiện hữu vẫn chạy sau mapping.

Ví dụ kiểm tra offline:

```python
from src.data_contracts import map_record

result = map_record(
    "ssi_v2", "stock_daily",
    {"Symbol": "SSI", "TradingDate": "18/06/2026", "ClosePrice": "25.5"},
    {"symbol": "SSI", "date": "18/06/2026"},
)
print(result.candidate)
print(result.report)
```

## Đăng ký mapping mới

1. Kiểm chứng API và ngữ nghĩa payload của nguồn một cách độc lập; mapping không thay auth, request hoặc pagination.
2. Chỉ dùng lại dataset chuẩn khi ý nghĩa và đơn vị khớp. Nếu contract ứng dụng đổi, cập nhật từ điển/version có chủ đích.
3. Thêm JSON nguồn với đúng `source_id`, dataset, `contract_version` tương thích, `mapping_version` mới và rule cho từng target.
4. Khai báo alias chính xác cùng transform có tên trong whitelist. Chỉ dùng `context` cho request context rõ ràng, `constant` cho giá trị cố định như `1m`, và chỉ dùng `unit_multiplier` khi có bằng chứng.
5. Nếu phép đổi phức tạp, thêm pure function vào `TRANSFORMS`; cấm biểu thức tùy ý và `eval`/`exec`.
6. Chạy `get_mapping(...)` và fixture offline, gồm missing, malformed, alias trùng/xung đột và field thừa.

Đã đăng ký cả `ssi_v2.json` và `ssi_v3.json`. Mapping SSI v3 `stock_daily` 2.0.0 đã production-ready: `remainForeignRoom` ánh xạ sang `foreign_remaining_room` canonical (room sở hữu nước ngoài còn lại), còn `totalForeignRoom` ánh xạ riêng sang `foreign_total_room` (tổng room sở hữu nước ngoài). SSI v2 mapping 2.0.0 vẫn là fallback deprecated explicit; alias nguyên bản `ForeignCurrentRoom` ánh xạ sang `foreign_remaining_room`, còn total room chưa xác minh được khai báo unsupported. SSI v3 `stock_intraday` và catalog vẫn preview-only. Alias qualified như `summary.close` chỉ tồn tại trong view mapping; raw payload không đổi.

`derived.py` dùng chung tính tổng giao dịch và net nước ngoài cho production lẫn Inspector với NULL propagation nghiêm ngặt. Contract 2.0.0 và database có `foreign_remaining_room`, `foreign_total_room` nullable; phép đổi tên giữ nguyên giá trị clean lịch sử và không cần backfill dữ liệu.

Xem [hướng dẫn inspector](../../scripts/ssi_api_inspector/README.vi.md).

`index_daily` là ngoại lệ đối với trạng thái v3 preview cũ: contract/mapping 2.0.0 là mapping production đã xác minh cho SSI v3 `indexSummary`. Identity lấy từ request context, mọi numeric optional giữ nullable, mapping không scale phần trăm. Mapping SSI v2 2.0 deprecated chỉ để tương thích inspection và không production-ready.
