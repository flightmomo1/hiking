# Changelog — IB3 baseline hiking performance weather numeric reattach closeout

## 2026-06-15

### Added

Documented closeout for:

`9af7f7d Add IB3 weather numeric reattach and gain-rate sanity check`

### Evidence summary

Weather numeric reattach:

- comparison rows: 25
- join rows: 26
- output rows: 25
- matched weather numeric reattach: 25
- partial reattach: 0
- missing join: 0
- audit: `PASS_WEATHER_NUMERIC_REATTACH_DESCRIPTIVE_ONLY`

Gain-rate sanity:

- `GAIN_RATE_LOW_REVIEW|GAIN_PER_KM_LOW_REVIEW`: 23
- `GAIN_RATE_PLAUSIBILITY_UNREVIEWED|GAIN_PER_KM_PLAUSIBILITY_UNREVIEWED`: 2

### Interpretation

The route-normalized comparison smoke now has numeric weather context reattached.

However, gain-related fields are not yet suitable for future ability estimation. The low gain-rate distribution should be treated as an elevation gain aggregation QA issue.

### Boundary

No ability score, rank, class, THCI score, radar score, or final hiking risk score was generated or authorized.
