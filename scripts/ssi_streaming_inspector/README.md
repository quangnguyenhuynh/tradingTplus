# SSI streaming inspector

Read-only CLI for Phase 0 SSI FastConnect Data streaming verification through classic SignalR.

## Documentation

- [English](README.md)
- [Tiếng Việt](README.vi.md)

The inspector connects to SSI streaming, subscribes to explicitly selected channels, decodes `Broadcast` messages, compares the actual content fields with the local stream registry, and prints sanitized diagnostics.

It never writes to Supabase and does not trigger ingest, feature, signal, or backtest pipelines.

For detailed CLI installation, commands, options, examples, output formats, statuses, and troubleshooting guidance, see the [Vietnamese guide](README.vi.md).
