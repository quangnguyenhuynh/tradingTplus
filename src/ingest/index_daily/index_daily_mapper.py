"""Provider-independent immutable index raw evidence."""
import hashlib
import json
from src.ingest.shared.date_utils import parse_index_date


def build_index_raw_daily_record(requested_code: str, date: str, payload: dict,
                                 *, source: str = "SSI_v3_indexSummary") -> dict:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return {"index_code": requested_code, "trading_date": parse_index_date(date).iso,
            "data_hash": hashlib.sha256(canonical.encode()).hexdigest(), "payload": payload, "source": source}
