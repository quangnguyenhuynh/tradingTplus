# SSI REST API Inspector

CLI **chỉ đọc** để xem trực tiếp response SSI mà không đi qua production ingest hoặc database. Công cụ in nguồn thực tế, endpoint, request đã che bí mật, envelope/paging/sample và tùy chọn raw JSON. `PASS` không chứng minh dữ liệu đầy đủ hay đúng ngữ nghĩa. Công cụ không chạy feature, signal hoặc backtest.

> Inspector mặc định REST v3. REST v2 là legacy và chỉ chạy khi truyền `--data-source ssi_v2`. Không fallback, không tự so sánh hai nguồn và không đổi source production.

## Cài đặt và credential

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

```env
# v3
SSI_API_KEY=replace_me
SSI_API_SECRET=replace_me
# legacy v2
SSI_CONSUMER_ID=replace_me
SSI_CONSUMER_SECRET=replace_me
```

V3 market data không cần credential v2, client ID, private key hay OTP. V2 không cần credential v3. Token chỉ giữ trong memory, không cache file. `list` và help không cần credential/network. Không in hoặc commit `.env`.

## CLI và ngày

```bash
python scripts/ssi_api_inspector/inspect.py --help
python scripts/ssi_api_inspector/inspect.py list
python scripts/ssi_api_inspector/inspect.py list --data-source ssi_v2
python scripts/ssi_api_inspector/inspect.py run <endpoint> [options]
python scripts/ssi_api_inspector/inspect.py run all [options]
```

Option: `--data-source`, `--symbol`, `--board`, alias tương thích `--market`/`--exchange`, `--index-code`, `--date`, `--from-date`, `--to-date`, `--page-index`, `--page-size`, `--limit`, `--full-json`, `--timeout`, `--ascending`. Ngày nhận `DD/MM/YYYY` hoặc `YYYY-MM-DD`. Dùng `--date` hoặc đủ cặp from/to (from <= to), không dùng chung. V3 summary/daily/master gửi `from`/`to` dạng `YYYY/MM/DD`; intraday gửi `from` lúc `00:00:00` và `to` lúc `23:59:59`, không dịch theo timezone máy. `index-summary`/`daily-index` chỉ nhận một ngày. Intraday cố định `1m`.

### Ánh xạ input ngày CLI sang query REST

| Source/endpoint | Query gửi đi | Timeframe |
|---|---|---|
| V3 `securities-summary` / `daily-stock-price` | `from`, `to` (`YYYY/MM/DD`) | không gửi |
| V3 `daily-ohlc` | `from`, `to` (`YYYY/MM/DD`) | `timeFrame=1d` |
| V3 `intraday-ohlc` | `from`, `to` (`YYYY/MM/DD HH:MM:SS`) | `timeFrame=1m` |
| V3 `master-data` | `from`, `to` (`YYYY/MM/DD`) | không gửi |
| V3 `index-summary` / `daily-index` | `tradingDate` (`YYYY/MM/DD`) | không gửi |
| Endpoint có ngày V2 | `FromDate`, `ToDate` (`DD/MM/YYYY`) | contract legacy; intraday giữ `resolution=1` |

`--page-size` là số record yêu cầu ở đúng một trang; `--limit` chỉ giới hạn sample được in. `--full-json` in toàn bộ response không qua mapper, không đổi field/type và chỉ redact bí mật.

## Endpoint

| V3 CLI | REST | Contract | Alias cũ |
|---|---|---|---|
| `access-token` | POST `/api/v3/auth/token` | JSON apiKey/apiSecret | — |
| `securities-by-board` | GET `/api/v3/data/securitiesByBoard` | đúng một symbol/board/index | `securities`, `securities-details`, `index-components` |
| `securities-summary` | GET `/api/v3/data/securitiesSummary` | đúng một symbol/index, ngày, paging | `daily-stock-price` |
| `index-list` | GET `/api/v3/data/indexList` | board tùy chọn | — |
| `index-summary` | GET `/api/v3/data/indexSummary` | đúng một board/index, một ngày | `daily-index` |
| `daily-ohlc` | GET `/api/v3/data/ohlc` | symbol, ngày, `timeFrame=1d`, paging | — |
| `intraday-ohlc` | GET `/api/v3/data/ohlc` | symbol, datetime, `timeFrame=1m`, paging | — |
| `master-data` | GET `/api/v3/data/masterdata` | ngày, paging; không symbol | — |

V2 giữ `access-token`, `securities`, `securities-details`, `index-components`, `index-list`, `daily-ohlc`, `intraday-ohlc`, `daily-index`, `daily-stock-price`; luôn thêm `--data-source ssi_v2`. Endpoint không có ở nguồn đã chọn báo lỗi, không đổi nguồn. `run all` chỉ gọi một lần mỗi data endpoint native của đúng nguồn, tự auth nhưng không report access-token riêng, dùng builder riêng, tiếp tục sau lỗi và in summary.

## Ví dụ

```bash
python scripts/ssi_api_inspector/inspect.py run access-token --full-json
python scripts/ssi_api_inspector/inspect.py run securities-by-board --board HOSE
python scripts/ssi_api_inspector/inspect.py run securities --market HOSE
python scripts/ssi_api_inspector/inspect.py run securities-details --symbol SSI
python scripts/ssi_api_inspector/inspect.py run index-components --index-code VNINDEX
python scripts/ssi_api_inspector/inspect.py run index-list --board HOSE
python scripts/ssi_api_inspector/inspect.py run securities-summary --symbol SSI --from-date 01/09/2026 --to-date 08/09/2026 --page-index 1 --page-size 20 --full-json
python scripts/ssi_api_inspector/inspect.py run securities-summary --symbol SSI --date 08/09/2026 --full-json
# Alias tương thích của cùng endpoint native v3:
python scripts/ssi_api_inspector/inspect.py run daily-stock-price --symbol SSI --date 08/09/2026 --full-json
python scripts/ssi_api_inspector/inspect.py run daily-index --index-code VNINDEX --date 08/09/2026 --full-json
python scripts/ssi_api_inspector/inspect.py run daily-ohlc --symbol SSI --date 2026-09-08
python scripts/ssi_api_inspector/inspect.py run intraday-ohlc --symbol SSI --date 08/09/2026 --page-index 1 --page-size 100 --full-json
python scripts/ssi_api_inspector/inspect.py run master-data --date 08/09/2026 --full-json
python scripts/ssi_api_inspector/inspect.py run all --symbol SSI --board HOSE --index-code VNINDEX --date 08/09/2026 --limit 3
```

Đối chiếu thủ công cùng mã/ngày (không có auto compare và không kết luận field tương đương):

```bash
python scripts/ssi_api_inspector/inspect.py run daily-stock-price --symbol SSI --date 08/09/2026 --full-json > /tmp/ssi-v3.txt
python scripts/ssi_api_inspector/inspect.py run daily-stock-price --data-source ssi_v2 --symbol SSI --date 08/09/2026 --full-json > /tmp/ssi-v2.txt
```

## Output, trạng thái và bảo mật

Report gồm source; endpoint native/alias; method; URL và params đã làm sạch; HTTP status; thời gian; Content-Type; rate-limit headers; top-level type/keys; vị trí list; số record của trang hiện tại; metadata provider `pageIndex/pageSize/pagesCount/itemsCount/totalRecord`; keys record đầu; sample; và full body khi yêu cầu.

- **PASS:** shape hợp lệ và có data; auth PASS khi có token.
- **EMPTY:** có list hợp lệ nhưng rỗng; không chứng minh ngày nghỉ.
- **FAILED:** lỗi transport/auth/HTTP/API, shape sai, body rỗng hoặc non-JSON.
- Exit `0` khi không FAILED, `1` khi có FAILED, lỗi cú pháp argparse là `2`.

Body JSON lỗi/4xx/5xx/non-JSON được giữ để report an toàn, không đổi thành `[]`. Key nhạy cảm nested (apiKey/apiSecret, consumer credential, token/refreshToken, Authorization...) được redact; giá trị secret/token bị echo trong text/exception được scrub. Redirect bị từ chối; retry mạng/429/5xx và phục hồi 401 đều hữu hạn; không ghi token ra file.

## Troubleshooting

- **401:** kiểm tra credential đúng nguồn; chỉ có tối đa một chu kỳ phục hồi auth.
- **403:** kiểm tra entitlement; không tự thêm OTP/private key.
- **429:** xem header rate limit/Retry-After; thời gian retry có trần.
- **Timeout/5xx:** dùng `--timeout` 1..120 hoặc thử lại; retry không vô hạn.
- **EMPTY:** kiểm tra mã/ngày/page/envelope; không tạo row giả hay kết luận ngày nghỉ.
- **Non-JSON/malformed:** dùng `--full-json` xem text đã scrub; status vẫn FAILED.

Tài liệu: [SSI API Reference](https://developers.ssi.com.vn/docs/api-reference) và [SSI FastConnect v3 tutorials](https://github.com/SSI-Securities-Inc/ssi-fastconnect-v3-tutorials). Nguồn contract: SSI API Reference và tutorial/request model FastConnect v3 chính thức. **Trạng thái live verification: UNVERIFIED / NOT_RUN trừ khi báo cáo triển khai cuối ghi khác.** Fixture offline tái hiện body `code=400` / `msg=invalid timeframe`, nhưng đó không phải response SSI đã quan sát và không chứng minh lỗi live người dùng báo đã được giải quyết.

## Test và live smoke chỉ đọc

```bash
pytest -q tests/inspectors/test_ssi_api_inspector.py
python -m compileall scripts/ssi_api_inspector
python scripts/ssi_api_inspector/inspect.py --help
python scripts/ssi_api_inspector/inspect.py list
python scripts/ssi_api_inspector/inspect.py list --data-source ssi_v2
```

Chỉ live smoke khi credential đã có sẵn, dùng mã/ngày rõ ràng. Inspector không đọc/ghi Supabase.
