# Precipitation and soil moisture datasets

Run `.\.venv-data\Scripts\python.exe -m ml.scripts.prepare_water_datasets` from the repository root. Requires numpy, pandas and rasterio. Outputs are in `data/prepared/water/` and raw sources are preserved.

Updated source support also requires h5py for daily GPM NetCDF4. Static layers use the newest coverage-validated collection. SMAP partial selections are combined by date, with the newer collection taking precedence on overlapping dates. NetCDF time coordinates are verified against measurement dates. GPM quality/error fields absent from a file remain missing, rather than being synthesized.

Two explicitly opt-in switches exist for exploratory policy changes: `--allow-missing-smap-error` permits missing uncertainty when recommended retrieval flags and finite surface metadata exist; `--provisional-late-targets` substitutes Late Run rain targets and values. These switches do not supply absent randomError predictors, so the precipitation dataset can still have no complete rows. They must be used in a separate output directory and do not satisfy the strict PDF contract. Default runs do not activate either switch.

The user authorized using available data and recording missing SMAP uncertainty.
Reproduce the usable recipe with:

```powershell
.\.venv-data\Scripts\python.exe -m ml.scripts.prepare_water_datasets --available-data --output data/prepared/available/water
```

This recipe uses Late Run rain inputs and targets and omits the unavailable GPM error predictor. Recommended SMAP AM retrievals with finite surface flags are accepted even when uncertainty is missing. The missing uncertainty is recorded in audit columns, never filled with zero. Because the exact daily moisture lags cannot be reconstructed from these sparse observations, the four exact lag predictors are omitted; the latest observed value and preceding seven-calendar-day mean remain. Both models require at least one valid antecedent SMAP observation within seven days. Precipitation retains its past-only seasonal moisture anomaly. Other required inputs must remain complete and finite.

`validation_report.json` supplies the exact feature list. Date, position, observation-count and uncertainty-availability columns are audit metadata, not extra model features. Precipitation targets require all seven daily observations; moisture targets average the valid observations in the target week and retain their count. These are observational targets, not interpolated daily moisture truth.

The extractor follows input lists from sections 2.3 and 2.4 of the provided specification, ignoring the subsequent deductions. It uses the nine existing POWER query locations, weekly Monday emission dates, antecedent windows ending at t-2, and labels between t+1 and t+7. Exact SMAP lags are 1, 3, 7 and 14 calendar days before the cutoff. No input is interpolated, spatially extrapolated, or replaced by a different product. POWER and rainfall aggregates require every day in their windows; the SMAP weekly target averages available valid measurements, recording their count.

Each model has a strict CSV, a candidate CSV explicitly marked NOT_FOR_TRAINING, and an excluded CSV listing missing fields. Strict CSVs contain only finite required inputs and targets. A machine-readable validation report lists source paths, policies, features, and counts. Targets are precipitation accumulated in mm and average surface moisture in m3/m3.

Screening choices that were not numerically defined in the PDF are explicit: rainy day means >0 mm/day; SMAP uses AM recommended retrievals (bits 0 and 1 unset), surface_flag=0, valid range 0.02–0.5, and uncertainty <=0.1 m3/m3 (configurable). The surface policy is deliberately conservative and needs review before practical deployment; terrain/vegetation flags can exclude usable observations. GPM quality and random error must be finite and nonnegative, but the PDF does not specify a scientific quality-index threshold. This remains a policy limitation even if complete files become available.

SMAP anomalies for precipitation use only the same ISO week from earlier calendar years, available before the cutoff. This avoids a baseline built from future observations. No earlier baseline means a missing input. Acquisition dates alone do not certify actual publication latency.

SoilGrids uses wv0033 as the server name for the document's wv003 field. Means are converted to g/kg (sand, silt, clay, soc), kg/dm3 (bdod), and m3/m3 (water). Uncertainty rasters are preserved in original scaled units. Static layers are sampled in their native containing pixel; dates are not assigned to static soil or terrain estimates.
