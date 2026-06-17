# Changelog update — 2026-06-17 — CH6.5.2 weather-adjusted behavior context v1

Added CH6.5.2 weather-adjusted behavior context evidence.

New script:
- scripts/make_ch6_5_2_weather_adjusted_behavior_context_v1.py

New output root:
- outputs/report_figures/ch6_5_2_weather_adjusted_behavior_context_v1

Latest run:
- activity_count: 25
- window_row_count: 2054
- weather_context_available_ratio: 1.0
- conservative_weather_review_required_windows_n: 2054
- behavior_weather_context_review_required_windows_n: 958
- audit_conclusion: PASS_CH6_5_2_WEATHER_ADJUSTED_BEHAVIOR_CONTEXT_V1_DESCRIPTIVE_ONLY

Sanity:
All windows triggered conservative weather review because RH is consistently high: min 88, avg 90.781, max 100. Additional UV, rain, and wind exposure contexts are present.

Boundary:
Descriptive evidence only. No ability score, ability rank, ability class, THCI score, radar score, final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, causality inference, or weather zero-fill is generated.
