# Analog migration cleanup guidance

Do not run cleanup automatically. Before V1 has production evidence, a DBA may
remove the additive schema in a maintenance window, in dependency order:

```sql
drop table if exists public.stock_analog_query_matches;
drop table if exists public.stock_analog_queries;
drop table if exists public.stock_analog_profile_reviews;
drop table if exists public.stock_analog_validation_runs;
drop table if exists public.stock_analog_outcomes;
drop table if exists public.stock_analog_snapshots;
drop table if exists public.stock_analog_profiles;
```

This destroys all Analog evidence. Export and count every table first. The
migration does not rewrite Phase 0 tables; its main deployment risks are the
brief catalog locks required by foreign keys to `stock_symbols` and policy creation.
