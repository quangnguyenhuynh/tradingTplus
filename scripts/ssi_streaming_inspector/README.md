# SSI streaming inspector

Read-only Phase 0 inspector for SSI FastConnect Data streaming/IDS/SignalR. It prints sanitized CLI diagnostics only: no Supabase writes, no DB mapping, no features/signals/backtests/derived fields.

Flow: SSI REST login -> SignalR negotiate -> websocket connect -> SignalR start -> `SwitchChannels` subscribe -> `Broadcast` frames -> wrapper (`DataType`/`Content`) -> decoded JSON content.

The SSI v2.2 streaming spec describes host/channels/payload examples, but not the complete classic SignalR handshake. Handshake details are therefore based on the current `SSIStreamingClient` and actual responses.

## Requirements

Environment: `SSI_CONSUMER_ID`, `SSI_CONSUMER_SECRET`, optional `SSI_STREAMING_ENABLED=true`, `SSI_STREAMING_BASE_URL`, `SSI_SIGNALR_PATH`, `SSI_SIGNALR_HUB`. Dependency: `websocket-client`.

## Channels

| CLI type | Channel | Meaning |
| --- | --- | --- |
| `securities-status` | `F:<symbol>` | status/session/trading status |
| `quote` | `X-QUOTE:<symbol>` | quote/orderbook levels |
| `trade` | `X-TRADE:<symbol>` | trades and market data |
| `foreign-room` | `R:<symbol>` | foreign room realtime |
| `index` | `MI:<index-code>` | realtime index data |
| `realtime-bar` | `B:<symbol>` | realtime OHLC bars |

`ALL` is never a default. If you pass an exact `--channel '*:ALL'`, expect high message volume.

## Commands

```bash
python scripts/ssi_streaming_inspector/inspect.py list
python scripts/ssi_streaming_inspector/inspect.py negotiate
python scripts/ssi_streaming_inspector/inspect.py run quote --symbols SSI --timeout 30 --max-messages 3
python scripts/ssi_streaming_inspector/inspect.py run trade --symbols SSI HPG --timeout 30 --max-messages 5
python scripts/ssi_streaming_inspector/inspect.py run index --index-codes VNINDEX VN30 --timeout 30
python scripts/ssi_streaming_inspector/inspect.py run all --symbols SSI --index-codes VNINDEX --timeout 60 --max-messages 2
python scripts/ssi_streaming_inspector/inspect.py run quote --channel X-QUOTE:SSI --raw-frames --full-json
```

Run during Vietnam market hours for best chance of messages. `PASS` means connected/subscribed and received messages. `EMPTY` means connected/subscribed but no message within timeout. `PARTIAL` is used by `all` when outcomes differ. `FAILED` identifies login/negotiate/connect/start/subscribe/listen errors.

Raw frames are sanitized before printing. Full JSON is also deep-redacted; do not share output until you have reviewed it.
