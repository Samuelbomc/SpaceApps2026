# Temperature dataset preparation

Run from the repository root:

```powershell
.\.venv-data\Scripts\python.exe -m ml.scripts.prepare_temperature_datasets
```

Dependencies: numpy, pandas, rasterio. Results are written to `data/prepared/temperature/`.

The three models share only the inputs required in section 2.2 of the provided specification. Their labels are the next seven days' average T2M, average T2M_MIN, and average T2M_MAX respectively. The latter two are weekly means of daily extrema, not the absolute minimum/maximum during the week.

Each example is a POWER query location and Monday emission date. Historical windows end two days before emission. All daily POWER and precipitation measurements in a window must be valid. Target windows require all seven days. SMAP uses recommended AM retrievals (quality bits 0 and 1 unset), a valid moisture range of 0.02–0.5, the latest antecedent valid measurement, and a mean of valid measurements in the preceding seven calendar days. Dates/counts of SMAP measurements are audit columns, not additional predictors. No future values or imputations are used.

Native raster cells are sampled at each POWER point with CRS transformation when needed. South-up GPM TIFFs are supported. Points outside a raster are invalid, never extrapolated. Query locations do not imply field-scale POWER accuracy; several locations may share a source cell. Keep all points from the same issue date together when later splitting temporally, and purge overlapping target windows across splits.

Outputs:

- `temperature_mean.csv`, `temperature_min.csv`, `temperature_max.csv`: strictly complete examples with target and required features.
- `*_excluded.csv`: every rejected example and its missing or invalid fields.
- `candidate_inputs_and_targets_NOT_FOR_TRAINING.csv`: intermediate extraction, including missing required inputs for inspection only.
- `validation_report.json`: counts, rules and exact input file inventory.

The extractor supports installed GPM Late Run (`3IMERGDL`) NetCDF4 files as well as daily precipitation GeoTIFFs. NetCDF sampling verifies time coordinates against measurement dates, variable units, dimension order, fill values and native spatial extent. Final Run is never substituted for Late Run inputs. Requires h5py in addition to the dependencies above.

Overlapping SMAP date selections are combined by measurement date; the newer collection path takes precedence for overlapping dates. Static rasters are selected from the newest collection with a passing coverage_validation.json. Earlier collections remain intact and are not mixed with the validated replacement.

The observation cutoff follows the specification, but archive measurement dates alone do not prove when a product became available. Publication-time validation is still necessary before claiming operational forecasting performance.
