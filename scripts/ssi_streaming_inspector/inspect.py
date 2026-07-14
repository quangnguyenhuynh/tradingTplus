#!/usr/bin/env python
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path
from typing import Any
SCRIPT_DIR = Path(__file__).resolve().parent; ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) in sys.path: sys.path.remove(str(SCRIPT_DIR))
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from src.config import config
from src.ssi.streaming import SSIStreamingClient
from scripts.ssi_streaming_inspector.registry import STREAM_TYPES, RUN_ALL_ORDER, build_channels
from scripts.ssi_streaming_inspector.output import decode_signalr_frame, dump_json, find_token_paths, inspect_arg, redact

STATUS_CODE = {"PASS": 0, "EMPTY": 0, "PARTIAL": 2, "FAILED": 1}

def print_connection(client: SSIStreamingClient, channels: list[str], timeout: int, counts: dict[str,int], status: str) -> None:
    info = {"streaming_base_url": config.SSI_STREAMING_BASE_URL, "signalr_path": config.SSI_SIGNALR_PATH, "hub_name": client.hub_name, "receive_method": config.SSI_SIGNALR_RECEIVE_METHOD, "switch_method": config.SSI_SIGNALR_SWITCH_METHOD, "client_protocol": client.client_protocol, "connection_id": client.connection_id, "connection_token": client.connection_token, "channels": channels, "timeout": timeout, "raw_frames": counts.get("raw_frames",0), "broadcast_payloads": counts.get("broadcasts",0), "status": status}
    print(dump_json(info))
    paths = find_token_paths(info)
    if paths: print(f"token_detected=true paths={paths}")

def list_types() -> int:
    for st in STREAM_TYPES.values():
        target = "index-codes" if st.target == "index_codes" else "symbols"
        print(f"{st.name}\t{st.prefix}:<{target}>\t{st.label}\tfields={len(st.expected_fields)}")
    return 0

def negotiate_only(args: argparse.Namespace) -> int:
    client = SSIStreamingClient()
    try:
        data = client.negotiate()
        print(dump_json({"status":"PASS", "negotiate": data, "signalr_url": client.signalr_url, "hub_name": client.hub_name, "client_protocol": client.client_protocol}))
        return 0
    except Exception as exc:
        print(dump_json({"status":"FAILED", "stage":"negotiate", "error": str(redact(str(exc)))})); return 1
    finally: client.close()

def _channels_for(kind: str, args: argparse.Namespace) -> list[str]:
    if args.channel: return build_channels(kind, exact_channel=args.channel)
    return build_channels(kind, symbols=args.symbols, index_codes=args.index_codes)

def run_kind(kind: str, args: argparse.Namespace) -> str:
    channels = _channels_for(kind, args)
    if not channels:
        print(dump_json({"status":"FAILED", "kind":kind, "error":"No channels built; pass --symbols/--index-codes or --channel"})); return "FAILED"
    if any(ch.upper().endswith(":ALL") for ch in channels):
        print("⚠️ ALL channel requested explicitly; output volume can be very large.")
    client = SSIStreamingClient(); counts={"raw_frames":0,"broadcasts":0}; messages=0; status="EMPTY"
    try:
        client.connect(); client.subscribe_many(channels); assert client.ws is not None
        client.ws.settimeout(1); deadline=time.monotonic()+args.timeout; seq=0
        while time.monotonic() < deadline and messages < args.max_messages:
            try: raw = client.ws.recv()
            except Exception as exc:
                timeout_exc = getattr(client._websocket_module, "WebSocketTimeoutException", None)
                if timeout_exc is not None and isinstance(exc, timeout_exc): continue
                print(dump_json({"status":"FAILED","stage":"listen","error":str(redact(str(exc)))})); status="FAILED"; break
            counts["raw_frames"] += 1
            frame = decode_signalr_frame(raw)
            if args.raw_frames: print("RAW_FRAME", dump_json(frame if args.full_json else {k:v for k,v in frame.items() if k != "raw"}))
            for msg in frame.get("messages", []):
                if str(msg.get("method") or "").lower() != config.SSI_SIGNALR_RECEIVE_METHOD.lower(): continue
                for arg in msg.get("args", []):
                    seq += 1; counts["broadcasts"] += 1; messages += 1; status="PASS"
                    req = channels[min(len(channels)-1, 0)]
                    out = inspect_arg(arg, kind if kind != "all" else None, req, seq, {**frame, "method": msg.get("method"), "args_count": msg.get("args_count")})
                    print("MESSAGE", dump_json(out if args.full_json else {k:v for k,v in out.items() if k != "decoded_content_sample"}))
                    if messages >= args.max_messages: break
                if messages >= args.max_messages: break
            if frame.get("malformed"):
                print("MALFORMED_FRAME", dump_json(frame))
        if status == "EMPTY":
            print("EMPTY: connected and subscribed, but no Broadcast message arrived. Check market hours, longer timeout, active symbol/index, exact channel, and account streaming permission.")
        return status
    except Exception as exc:
        print(dump_json({"status":"FAILED", "kind":kind, "channels":channels, "error":str(redact(str(exc)))})); return "FAILED"
    finally:
        print_connection(client, channels, args.timeout, counts, status)
        client.close()

def build_parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="Read-only SSI FastConnect SignalR streaming inspector.")
    sub=p.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    neg=sub.add_parser("negotiate"); neg.add_argument("--timeout", type=int, default=30)
    run=sub.add_parser("run"); run.add_argument("kind", choices=[*STREAM_TYPES.keys(), "all"]); run.add_argument("--symbols", nargs="+", default=["SSI"]); run.add_argument("--index-codes", nargs="+", default=["VNINDEX"]); run.add_argument("--timeout", type=int, default=30); run.add_argument("--max-messages", type=int, default=3); run.add_argument("--limit", type=int, default=None); run.add_argument("--full-json", action="store_true"); run.add_argument("--raw-frames", action="store_true"); run.add_argument("--channel"); run.add_argument("--negotiate-only", action="store_true")
    return p

def main(argv: list[str]|None=None) -> int:
    args=build_parser().parse_args(argv)
    if getattr(args,"limit",None) is not None: args.max_messages=args.limit
    if args.command=="list": return list_types()
    if args.command=="negotiate" or getattr(args,"negotiate_only",False): return negotiate_only(args)
    kinds = RUN_ALL_ORDER if args.kind == "all" else (args.kind,)
    results={k: run_kind(k,args) for k in kinds}
    overall = "PASS" if all(v=="PASS" for v in results.values()) else "EMPTY" if all(v=="EMPTY" for v in results.values()) else "FAILED" if all(v=="FAILED" for v in results.values()) else "PARTIAL"
    print("SUMMARY", dump_json({"overall": overall, "results": results}))
    return STATUS_CODE[overall]
if __name__ == "__main__": raise SystemExit(main())
