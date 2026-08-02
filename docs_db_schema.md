
## `replace_features_atomic` RPC (2026-08-02)
`public.replace_features_atomic(text,text,timestamptz,timestamptz,jsonb)` atomically replaces one exact `features` symbol/timeframe/half-open UTC range. It rejects wildcard/blank symbols, non-persisted timeframes, invalid ranges, empty/out-of-scope/duplicate payloads, and returns deleted/replaced counts. Execute is revoked from `PUBLIC`, `anon`, and `authenticated`, and granted only to `service_role`. Migration: `migrations/20260802_atomic_replace_features.sql`. Applying it changes no rows; an explicit later replace changes only its exact scope.
