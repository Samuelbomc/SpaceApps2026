# Daily forecast leads

Every output supports integer lead_days 1 through 60. A lead H predicts only target_date = issue_date + H days.

| Output | Individual-day target |
|---|---|
| temperature_mean | That day's mean air temperature, C |
| temperature_min | That day's minimum air temperature, C |
| temperature_max | That day's maximum air temperature, C |
| precipitation | That day's total rainfall, mm/day |
| moisture | Mean of that day's accepted AM/PM SMAP retrievals, m3/m3 |

Issue date November 15, 2026 therefore forecasts November 16 through January 14, 2027. Models can use any later issue date when fresh, finite features are supplied. The historical training end does not bound forecast target dates.

Weather/rain/SMAP features end at t-2; radiation ends at t-7. Known target-date calendar features and lead_days distinguish future dates. Current inference inputs are in data/prepared/daily/<output>/inference.csv. One model per output serves all leads; there is no recursive feeding of model predictions.

The existing ForecastPredictor(output, horizon_days=H) call is supported. When a frame has lead_days, its per-row lead is used; otherwise H supplies the lead. The default remains H=7 for constructor compatibility.

All 60 per-lead test scores are in ml/artifacts/forecasts/lead_metrics.csv. Selected leads and pooled results are in [seven-day-results.md](seven-day-results.md). Daily target errors cannot be compared directly against earlier multi-day aggregate errors.
