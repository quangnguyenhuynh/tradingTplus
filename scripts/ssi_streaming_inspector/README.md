# SSI streaming inspector

Read-only CLI for Phase 0 SSI FastConnect Data streaming verification through classic SignalR.

The inspector connects to SSI streaming, subscribes to explicitly selected channels, decodes `Broadcast` messages, compares the actual content fields with the local stream registry, and prints sanitized diagnostics. It never writes to Supabase or any