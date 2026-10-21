from __future__ import annotations
import argparse
import json
from typing import Any

def _status_to_exit(summary: dict[str, Any]) -> int:
    return 1 if summary.get("status") == "FAILED" else 0

def _print_summary(summary: Any) -> None:
    if isinstance(summary, dict):
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))

def _source_kwargs(args: argparse.Namespace) -> dict[str, str]:
    """Preserve legacy callable compatibility unless the option was explicit."""
    return {"data_source": args.data_source} if getattr(args, "data_source", None) is not None else {}
