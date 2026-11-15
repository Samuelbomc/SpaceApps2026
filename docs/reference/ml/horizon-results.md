# Forecast horizons

All five outputs use rolling-origin training at 7, 15, 30 and 60 days. Features end at issue date t minus two days; targets cover t+1 through t+H.

| Output | Target |
|---|---|
| temperature_mean | Mean daily mean temperature, C |
| temperature_min | Mean daily minimum temperature, C |
| temperature_max | Mean daily maximum temperature, C |
| precipitation | Accumulated rainfall over the complete horizon, mm |
| moisture | Mean valid SMAP moisture observations during the horizon, m3/m3 |

Temperature minima/maxima are averages of daily extrema, not the coldest/hottest individual observation. Moisture labels can contain as little as one observed day; median target coverage is about 11/15, 20/30 and 34/60 days. Observation counts remain audit metadata.

Datasets are in `data/prepared/expanded/` for seven days and `data/prepared/horizons/<horizon>d/` for longer horizons. Models are in `ml/artifacts/forecasts/<horizon>d/<model_name>/`.

Run `python -m ml.scripts.train_rolling_origin`, then `python -m ml.scripts.validate_rolling_origin` and `python -m ml.scripts.summarize_rolling_origin`. Each command defaults to all horizons.

See [rolling-origin-results.md](rolling-origin-results.md) for selection and [seven-day-results.md](seven-day-results.md) for current scores and limitations. Forecasts are period aggregates, not daily trajectories or predictions for the endpoint day.
