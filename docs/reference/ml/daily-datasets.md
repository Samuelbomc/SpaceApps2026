# Direct daily forecasting datasets

The full prepared tables and pair indexes stay local and are excluded from Git. Model inference from a fresh checkout uses the committed production weights and the small snapshot in ml/examples; it does not need these training tables. See [ML README](../../../ml/README.md) for inference setup. Source downloads and local evaluation artifacts are required only to reproduce preparation, training or full holdout validation.

The current models predict individual future days at leads 1 through 60. This replaces period-average temperature/moisture and accumulated multi-day rainfall targets. The output-named daily models use purged rolling-origin selection; verified scores are in [seven-day-results.md](seven-day-results.md).

## Forecast readiness and source cutoffs

Prepared issue date: **November 15, 2026** (America/Bogota). Daily prediction inputs cover **November 16, 2026 through January 14, 2027**, with nine POWER locations for each temperature/rainfall output and 175 native SMAP cells for moisture.

Weather, rainfall and SMAP inputs have a measurement cutoff of November 13 (t-2); radiation ends November 8 (t-7). Actual latest measurements are November 12 for POWER temperature and GPM rainfall, November 11 for accepted moisture, and November 10 for POWER radiation. Bounded causal input filling bridges recent gaps. Older observations carry explicit ages and fill counts. This demonstrates finite input readiness, not independently verified historical publication-time availability or forecast accuracy.

| Output | Daily labels | Lead-1 training pairs | All lead-1..60 pairs | Latest target observation | Latest lead-1 training issue |
|---|---:|---:|---:|---|---|
| temperature_mean | 49,293 | 49,005 | 2,924,370 | 2026-11-12 | 2026-11-11 |
| temperature_min | 49,293 | 49,005 | 2,924,370 | 2026-11-12 | 2026-11-11 |
| temperature_max | 49,293 | 49,005 | 2,924,370 | 2026-11-12 | 2026-11-11 |
| precipitation | 49,275 | 48,987 | 2,923,290 | 2026-11-12 | 2026-11-11 |
| moisture | 266,283 | 264,461 | 15,311,697 | 2026-11-11 | 2026-11-10 |

Daily labels count real observed point/date records, including early records without enough preceding feature history. Pair counts link a usable historical feature row to a real daily observation at the selected lead. Reusing a daily label at different leads does not create independent observations.

## Exact targets

- temperature_mean: POWER T2M on target_date, C.
- temperature_min: POWER T2M_MIN on target_date, C; that day's minimum, not a period average.
- temperature_max: POWER T2M_MAX on target_date, C; that day's maximum.
- precipitation: GPM Late daily precipitation on target_date, mm for that day.
- moisture: mean accepted AM/PM SMAP soil moisture on target_date, m3/m3; one available retrieval is sufficient.

Only the selected target day must be observed. The missing November 8 GPM file excludes targets for November 8; November 9-12 labels remain usable. No targets are interpolated, forward-filled or replaced by zero. Temperature labels do not average neighbouring days, and moisture targets no longer average over an entire horizon.

## Input fields

Each output's exact ordered predictor list is in `data/prepared/daily/manifest.json` under models/output/features. There are 53 predictors per climate output and 75 for moisture.

The historical block retains 7/14/30-day POWER temperature, minimum/maximum temperature, RH2M, QV2M and WS2M means; latest T2M; lagged seven-day radiation; GPM 1/3/7/14/30-day sums, seven-day daily maximum and rainy-day count; elevation; and issue-date seasonal calendar fields. These historical aggregates are predictors, not targets.

New daily predictors include each POWER variable's latest daily value and observation age, GPM observation age, historical input-fill counts and the static-imputation count. The latest daily meteorology is lagged two days; radiation is lagged seven days. Ages measure additional staleness relative to the variable's cutoff.

Moisture adds recent seven-day SMAP mean, last valid moisture, age, observed-day count, past non-recommended-retrieval count, SRTM slope and SoilGrids 0-5 cm mean/uncertainty for sand, silt, clay, SOC, bulk density, wv0010, wv0033 and wv1500. Future retrieval/quality counts live only beside labels and are excluded from predictors.

Every joined training row and prediction row adds known future fields: `lead_days` (1..60), `target_day_of_year_sin`, `target_day_of_year_cos`, and `target_week_of_year`. `target_date = issue_date + lead_days`. Dates, coordinates and IDs remain metadata unless explicitly included in the predictor list.

The relaxed source policy remains: attempted, finite SMAP retrievals in 0.02-0.50 are retained even when non-recommended; missing uncertainty does not reject observations. Causal input carry-forward limits are seven days for POWER, three for rainfall, and fourteen for SMAP. Missing static fields use the nearest available sampled location and are flagged. Many SMAP labels are non-recommended and may be noisy. POWER uses LST calendar days; GPM/SMAP use UTC days. Same-date covariates are not identical 24-hour intervals. No publication-time archive or new fine-resolution weather is claimed.

## Files and loading

Each directory in `data/prepared/daily/<output>/` contains:

| File | Role |
|---|---|
| features.csv | Historical finite predictor rows, feature_id, point_id, issue date and cutoffs; no target |
| labels.csv | Actual daily observations with label_id, point_id, target_date, target and optional quality metadata |
| pairs/lead_01.npz through lead_60.npz | Integer feature_id/label_id pairs for each lead |
| inference.csv | Label-free November 15 predictor rows for all 60 leads, including target calendar fields |

Pair indexes avoid copying the large feature tables sixty times. The normalized representation is about 585 MB. Use the supplied loader to obtain ordinary complete training batches:

```python
from ml.datasets.daily import iter_training_batches

for batch in iter_training_batches("precipitation", leads=range(1, 61), batch_size=65536):
    # Select the ordered features from the manifest and batch["target"].
    # This reads data; it does not fit any model.
    pass
```

The loader also returns target_start and target_end, both equal to target_date, for future temporal purging. Never randomly split the expanded pairs. Rolling-origin validation must group issue dates across locations and leads and purge training labels whose target_date reaches the next partition's observation cutoff. The input lag and maximum target date determine eligibility, not merely a row's issue date.

## Reproduce without training

```powershell
.\.venv-data\Scripts\python.exe -B -m ml.scripts.prepare_daily_datasets --issue-date 2026-11-15
.\.venv-data\Scripts\python.exe -B -m ml.scripts.validate_daily_datasets
```

Omit --issue-date to use the current America/Bogota date. Available input freshness still constrains how far the existing downloads support a later issue date.

Validation reconstructs every daily label from raw source observations, checks every lead's pair indexes, checks inference field/calendar alignment and tests invariance to post-cutoff weather changes. Results are written to `data/prepared/daily/validation.json`.

## Training and previous iterations

The aggregate datasets in expanded/ and horizons/ remain historical preparations. Their trained binaries have been replaced by the five current direct-daily models. train_rolling_origin.py now delegates to train_daily_models.py, fitting every accepted pair at leads 1-60 using memory-efficient quantile matrices. validate_rolling_origin.py and summarize_rolling_origin.py validate and document the daily artifacts. ForecastPredictor and sample_forecasts.py use the new daily inputs while preserving output names and the horizon_days constructor argument. See [rolling-origin-results.md](rolling-origin-results.md) for the purged selection protocol.
