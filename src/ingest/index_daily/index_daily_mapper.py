"""Provider-independent immutable index raw evidence."""
import hashlib
import json
from src.contracts.numeric import exact_json_dumps
from src.ingest.shared.date_utils import parse_index_date


def build_index_raw_daily_record(requested_code: str, date: str, payload: dict,
                                 *, source: str = "SSI_v3_indexSummary") -> dict:
    canonical = exact_json_dumps(payload, sort_keys=True)
    return {"index_code": requested_code, "trading_date": parse_index_date(date).iso,
            "data_hash": hashlib.sha256(canonical.encode()).hexdigest(), "payload": payload, "source": source}
