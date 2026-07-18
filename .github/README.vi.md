# Cấu hình GitHub

Cấu hình automation và cộng tác cấp repository trên GitHub.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Nội dung

- [`workflows/`](workflows/README.vi.md): CI, job ingest theo lịch và feature job chạy manual.

## Quy tắc

- Workflow phải giữ tách biệt ingest, validation, feature, signal và backtest.
- Secret phải lấy từ GitHub Actions secrets và không được in ra log.
- Job ghi production phải dùng command rõ ràng và phạm vi có giới hạn.
- Thay đổi workflow nên được kiểm tra qua pull request trước khi merge vào `dev`.

Xem README trong `workflows/` để biết lịch và command hiện tại.
