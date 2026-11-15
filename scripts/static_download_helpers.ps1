# Shared setup for SRTM and SoilGrids. Caller supplies original AOI parameters.
if ([string]::IsNullOrWhiteSpace($PythonExecutable)) {
    $PythonExecutable = Join-Path $PSScriptRoot "..\.venv-data\Scripts\python.exe"
}
if ([string]::IsNullOrWhiteSpace($PowerDirectory)) {
    $PowerDirectory = Join-Path $PSScriptRoot "..\data\POWER"
}
function Initialize-StaticDownload {
    if ([double]::IsNaN($BufferDegrees) -or [double]::IsInfinity($BufferDegrees) -or $BufferDegrees -le 0) {
        throw "BufferDegrees must be finite and greater than zero."
    }
    if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
        throw "PythonExecutable not found. Use the extraction environment with numpy and rasterio."
    }
    & $PythonExecutable -c "import numpy, rasterio"
    if ($LASTEXITCODE -ne 0) { throw "The validation environment requires numpy and rasterio." }
}

function Confirm-StaticDownload {
    param([int]$ExpectedCount)
    & $PythonExecutable (Join-Path $PSScriptRoot "validate_static_coverage.py") $OutputDirectory `
        --power-directory $PowerDirectory --bbox $LongitudeMinimum $LatitudeMinimum $LongitudeMaximum $LatitudeMaximum --expected-count $ExpectedCount
    if ($LASTEXITCODE -ne 0) {
        throw "Raster validation failed. See coverage_validation.json; do not use this download for training."
    }
}
