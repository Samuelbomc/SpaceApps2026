[CmdletBinding()]
param(
    [double]$LatitudeMinimum = 5.4110,
    [double]$LatitudeMaximum = 6.5866,
    [double]$LongitudeMinimum = -75.5830,
    [double]$LongitudeMaximum = -74.6167,
    [string]$OpenTopographyApiKey = $env:OPENTOPOGRAPHY_API_KEY,
    [string]$WhiteboxToolsExecutable = "whitebox_tools",
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"

if ($LatitudeMinimum -lt -90 -or $LatitudeMaximum -gt 90 -or $LatitudeMinimum -ge $LatitudeMaximum) {
    throw "LatitudeMinimum and LatitudeMaximum must be ordered values between -90 and 90."
}
if ($LongitudeMinimum -lt -180 -or $LongitudeMaximum -gt 180 -or $LongitudeMinimum -ge $LongitudeMaximum) {
    throw "LongitudeMinimum and LongitudeMaximum must be ordered values between -180 and 180."
}
if ([string]::IsNullOrWhiteSpace($OpenTopographyApiKey)) {
    throw "Set OPENTOPOGRAPHY_API_KEY or pass -OpenTopographyApiKey. Create a free key at OpenTopography before running this script."
}

$whitebox = Get-Command $WhiteboxToolsExecutable -ErrorAction SilentlyContinue
if ($null -ne $whitebox) {
    $whiteboxPath = $whitebox.Source
}
else {
    $bundledWhitebox = Join-Path $PSScriptRoot "..\tools\whiteboxtools\WhiteboxTools_win_amd64\WBT\whitebox_tools.exe"
    if (-not (Test-Path -LiteralPath $bundledWhitebox -PathType Leaf)) {
        throw "WhiteboxTools was not found. Install it, use the repository-local binary, or rerun with -WhiteboxToolsExecutable <path>; it is required to calculate slope, flow direction, and flow accumulation."
    }
    $whiteboxPath = (Resolve-Path -LiteralPath $bundledWhitebox).Path
}

$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmssZ")
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $PSScriptRoot "..\SRTM\SRTMGL1_${timestamp}"
}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path

$culture = [System.Globalization.CultureInfo]::InvariantCulture
$south = $LatitudeMinimum.ToString("0.####", $culture)
$north = $LatitudeMaximum.ToString("0.####", $culture)
$west = $LongitudeMinimum.ToString("0.####", $culture)
$east = $LongitudeMaximum.ToString("0.####", $culture)
$demPath = Join-Path $OutputDirectory "srtmgl1_dem_raw.tif"

$query = @{
    demtype = "SRTMGL1"
    south = $south
    north = $north
    west = $west
    east = $east
    outputFormat = "GTiff"
    API_Key = $OpenTopographyApiKey
}
$queryString = ($query.GetEnumerator() | ForEach-Object {
    "{0}={1}" -f [uri]::EscapeDataString($_.Key), [uri]::EscapeDataString([string]$_.Value)
}) -join "&"
$requestUrl = "https://portal.opentopography.org/API/globaldem?$queryString"

Write-Host "Downloading SRTMGL1 DEM..."
Invoke-WebRequest -Uri $requestUrl -OutFile $demPath
if ((Get-Item -LiteralPath $demPath).Length -eq 0) {
    throw "OpenTopography returned an empty SRTM DEM."
}

$filledDemPath = Join-Path $OutputDirectory "srtmgl1_dem_filled_for_hydrology.tif"
$slopePath = Join-Path $OutputDirectory "srtmgl1_slope_degrees.tif"
$flowDirectionPath = Join-Path $OutputDirectory "srtmgl1_d8_flow_direction.tif"
$flowAccumulationPath = Join-Path $OutputDirectory "srtmgl1_d8_flow_accumulation_cells.tif"

function Invoke-WhiteboxTool {
    param([string[]]$Arguments)
    & $whiteboxPath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "WhiteboxTools failed: $($Arguments -join ' ')"
    }
}

Write-Host "Deriving filled DEM, slope, D8 flow direction, and D8 flow accumulation..."
Invoke-WhiteboxTool @("-r=FillDepressions", "-v", "--dem=$demPath", "--output=$filledDemPath", "--fix_flats")
Invoke-WhiteboxTool @("-r=Slope", "-v", "--dem=$demPath", "--output=$slopePath", "--units=degrees")
Invoke-WhiteboxTool @("-r=D8Pointer", "-v", "--dem=$filledDemPath", "--output=$flowDirectionPath")
Invoke-WhiteboxTool @("-r=D8FlowAccumulation", "-v", "--input=$flowDirectionPath", "--output=$flowAccumulationPath", "--out_type=cells", "--pntr")

$manifest = [ordered]@{
    source = "SRTM GL1 through OpenTopography Global DEM API"
    downloaded_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    geographic_bounds = [ordered]@{
        latitude_minimum = $LatitudeMinimum
        latitude_maximum = $LatitudeMaximum
        longitude_minimum = $LongitudeMinimum
        longitude_maximum = $LongitudeMaximum
    }
    raw_dem = (Split-Path -Leaf $demPath)
    derived_layers = @{
        filled_dem = (Split-Path -Leaf $filledDemPath)
        slope_degrees = (Split-Path -Leaf $slopePath)
        d8_flow_direction = (Split-Path -Leaf $flowDirectionPath)
        d8_flow_accumulation_cells = (Split-Path -Leaf $flowAccumulationPath)
    }
    dem_request_url = $requestUrl.Replace($OpenTopographyApiKey, "REDACTED")
    hydrology_method = "WhiteboxTools FillDepressions with fix_flats, D8Pointer, and D8FlowAccumulation with pntr=true"
    conditioning_applied = $false
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $OutputDirectory "manifest.json") -Encoding utf8
Write-Host "Saved SRTM source and derived layers to: $OutputDirectory"
