# Foreign EOD features

This independent derived pipeline reads only `stock_daily`. A verified calendar
JSON (`source`, `market`, `sessions`) defines rolling sessions; without it the
pipeline reports `WINDOW_UNVERIFIED`. Money is VND. Ratios are fractions using
`total_traded_value`; activity is buy plus sell and its ratio denominator is
twice total traded value. NULL means incomplete fields/history or an invalid
denominator, never zero. SSI's exact matched/deal/odd-lot coverage remains a
source limitation and the ratio must not be advertised as a unique whole-market
participation measure.

Fingerprint identity includes formula version, calendar identity, expected
sessions, row presence, and relevant source values. `created_at` is preserved by
upsert; `updated_at` identifies the write, not source chronology.
