# Data-acquisition scripts

The raster acquisition scripts documented here use these default geographic bounds:

- South: 5.4110
- North: 6.5866
- West: -75.5830
- East: -74.6167

They save each acquisition in a source-specific folder at the repository root and include a `manifest.json` with the spatial extent, source, requested variables, and source request metadata. They intentionally do not create model features or training splits.

SRTM and SoilGrids save under `data/SRTM/` and `data/SOILGRIDS/`.
Their requested bounds include a configurable `-BufferDegrees 0.01` margin
(about 1 km) around the original AOI. This prevents clipping or pixel alignment
from excluding POWER query points at the eastern boundary. The manifest keeps
both the original AOI and the expanded download bounds.

These two scripts require the repository-local `.venv-data` Python environment
with numpy and rasterio, or an explicit `-PythonExecutable` path. At completion
they validate every output TIFF at the four AOI corners and every POWER query
point in `data/POWER/`, requiring finite, non-NoData values. Missing rasters,
outside coordinates, or invalid values fail the script and are recorded in
`coverage_validation.json`. Only collections with `passed: true` should be used.
Older collections are retained; do not combine duplicate versions in extraction.

The SRTM buffer addresses raster-edge coverage. It does not guarantee full
upstream catchment coverage for flow accumulation: a watershed-scale DEM is
needed when catchments extend beyond this download rectangle.

## SRTM

`fetch_srtm.ps1` downloads the SRTM GL1 (approximately 30 m) DEM from OpenTopography and derives:

- slope in degrees;
- depression-filled DEM used only for hydrology;
- D8 flow direction;
- D8 flow accumulation in upstream cell counts.

It requires an OpenTopography API key and a local [WhiteboxTools](https://www.whiteboxgeo.com/manual/wbt_book/intro.html) executable.

```powershell
$env:OPENTOPOGRAPHY_API_KEY = "your-key"
powershell -ExecutionPolicy Bypass -File .\scripts\fetch_srtm.ps1
```

## SoilGrids 2.0

`fetch_soilgrids.ps1` downloads GeoTIFF WCS subsets for depth `0-5cm` using the mean and uncertainty layers of `sand`, `silt`, `clay`, `soc`, `bdod`, `cfvo`, `wv0010`, `wv0033`, and `wv1500`.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\fetch_soilgrids.ps1
```

## Sentinel-2 Level-2A

`fetch_sentinel2_l2a.ps1` selects the newest catalog scene within the configurable cloud-cover threshold and downloads `B04`, `B08`, and `SCL` in 0.1-degree tiles. Each output is requested on an approximately 10 m grid. `SCL` is resampled by nearest neighbour so its class values remain categorical.

It requires a Copernicus Data Space OAuth client.

```powershell
$env:CDSE_CLIENT_ID = "your-client-id"
$env:CDSE_CLIENT_SECRET = "your-client-secret"
powershell -ExecutionPolicy Bypass -File .\scripts\fetch_sentinel2_l2a.ps1
```

The manifest records the catalog acquisition time and catalog cloud percentage. SCL still needs to be used during later conditioning to mask clouds and shadows before NDVI is calculated.
