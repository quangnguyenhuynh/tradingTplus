#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
import argparse, json
from contextlib import redirect_stdout
from src.ingest.shared.date_utils import parse_ddmmyyyy
from src.quality.completeness.ingest_check import check_ingest

def main(argv=None):
    parser = argparse.ArgumentParser(description="Check ingest completeness")
    parser.add_argument("--date", required=True)
    parser.add_argument("--symbols", nargs="+", default=None)
    args = parser.parse_args(argv)
    try:
        parse_ddmmyyyy(args.date)  # Reject invalid input before DB construction.
        # Existing completeness functions print progress; keep stdout JSON-only.
        with redirect_stdout(sys.stderr):
            result = check_ingest(args.date, symbols=args.symbols)
    except ValueError:
        print(json.dumps({"status": "UNKNOWN", "error_type": "INVALID_INPUT", "read_only": True,
                          "reason": "Invalid date/scope or unsupported check invocation"}))
        return 2
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error_type": type(exc).__name__, "read_only": True,
                          "reason": "Completeness query failed; credentials and remote exception details omitted"}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    status = result.get("status") if isinstance(result, dict) else None
    return {"OK": 0, "PARTIAL": 1, "FAILED": 1}.get(status, 2) if isinstance(status, str) else 2
if __name__ == "__main__":
    raise SystemExit(main())
