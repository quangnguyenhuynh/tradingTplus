# SSI REST API inspector

Read-only CLI for Phase 0 SSI FastConnect Data REST verification.

The inspector sends direct HTTP requests to SSI, prints the raw response envelope in a readable form, and never writes to Supabase or any database. Its purpose is to verify the real SSI response shape, parameters, paging, empty responses, and field availability before changing ingest or clean-data pipelines.

## Scope and safety

- Read-only for database state.
- Does not import `SupabaseClient`.
- Does not insert, update, upsert, or delete data.
- Automatically obtains an SSI access token when an authenticated endpoint is called.
- Retries authentication once when SSI returns HTTP `401`.
- Redacts consumer credentials, bearer tokens, authorization headers, and nested token-like keys before printing output.

Do not share complete CLI output blindly. Even after token redaction, an SSI response can still contain market, symbol, or account-related context.

## Requirements

Run commands from the project root.

Install the project dependencies in the active Python environment