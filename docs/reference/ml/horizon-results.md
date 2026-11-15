# Daily forecast leads

Every output supports integer lead_days 1 through 60. A lead H predicts only target_date = issue_date + H days.

The issue date is the day on which the forecast is issued. The observation cutoff is the latest measurement date allowed into its inputs. The target date is the future date being predicted; these three dates serve different purposes.

| Lead | Target date for issue November 15, 2026 |
|---|---|
| 1 | November 16, 2026 |
| 7 | November 22, 2026 |
| 15 | November 30, 2026 |
| 30 | December 15, 2026 |
| 60 | January 14, 2027 |

From the repository root, run `python -m ml.sample_forecasts --example` for all of the next seven days, `--example --days 14` for leads 1-14, or `--example --leads 1 7 15 30 60` for only those five target dates. `--format json` selects structured output. Lead 0 (today) is not part of the trained 1-60 range.

| Output | Individual-day target |
|---|---|
| temperature_mean | That day's mean air temperature, C |
| temperature_min | That day's minimum air temperature, C |
| temperature_max | That day's maximum air temperature, C |
| precipitation | That day's total rainfall, mm/day |
| moisture | Mean of that day's accepted AM/PM SMAP retrievals, m3/m3 |

Issue date November 15, 2026 therefore forecasts November 16 through January 14, 2027. Models can use any later issue date when fresh, finite features are supplied. The historical training end does not bound forecast target dates.

Weather/rain/SMAP features end at t-2; radiation ends at t-7. Known target-date calendar features and lead_days distinguish future dates. Current inference inputs are in data/prepared/daily/<output>/inference.csv. One model per output serves all leads; there is no recursive feeding of model predictions.

The local inference files are excluded from Git. Committed examples in `ml/examples/inputs/` provide the same daily input schema at one location per output. Their dates are a fixed snapshot, not live observations. The sample prints the actual issue date and coordinates; climate and moisture use different native grid locations.

The existing ForecastPredictor(output, horizon_days=H) call is supported. When a frame has lead_days, its per-row lead is used; otherwise H supplies the lead. The default remains H=7 for constructor compatibility.

All 60 per-lead test scores are in ml/artifacts/forecasts/lead_metrics.csv. Selected leads and pooled results are in [model-results.md](seven-day-results.md). Daily target errors cannot be compared directly against earlier multi-day aggregate errors.

The pooled score combines all 60 leads and can hide weaker individual days: moisture does not beat persistence at leads 1-3 in this run. Nearby future days can also receive identical predictions because XGBoost trees produce piecewise-constant outputs. Repeated values are not evidence of equal real future conditions or zero uncertainty.
