[CmdletBinding()]
param(
    [double]$LatitudeMinimum = 5.4110,
    [double]$LatitudeMaximum = 6.5866,
    [double]$LongitudeMinimum = -75.5830,
    [double]$LongitudeMaximum = -74.6167,
    [double]$BufferDegrees = 0.01,
    [string]$PythonExecutable = "",
    [string]$PowerDirectory = "",
    [int]$ResolutionMeters = 250,
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "static_download_helpers.ps1")
Initialize-StaticDownload

if ($LatitudeMinimum -lt -90 -or $LatitudeMaximum -gt 90 -or $LatitudeMinimum -ge $LatitudeMaximum) {
    throw "LatitudeMinimum and LatitudeMaximum must be ordered values between -90 and 90."
}
if ($LongitudeMinimum -lt -180 -or $LongitudeMaximum -gt 180 -or $LongitudeMinimum -ge $LongitudeMaximum) {
    throw "LongitudeMinimum and LongitudeMaximum must be ordered values between -180 and 180."
}
if ($ResolutionMeters -lt 1) {
    throw "ResolutionMeters must be positive."
}

$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmssZ")
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $PSScriptRoot "..\data\SOILGRIDS\SOILGRIDS_V2_0_0-5cm_BUFFERED_${timestamp}"
}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path

$culture = [System.Globalization.CultureInfo]::InvariantCulture
$south = [Math]::Max([double]-90, [double]($LatitudeMinimum - $BufferDegrees))
$north = [Math]::Min([double]90, [double]($LatitudeMaximum + $BufferDegrees))
$west = [Math]::Max([double]-180, [double]($LongitudeMinimum - $BufferDegrees))
$east = [Math]::Min([double]180, [double]($LongitudeMaximum + $BufferDegrees))
$latMin = $south.ToString("0.########", $culture)
$latMax = $north.ToString("0.########", $culture)
$lonMin = $west.ToString("0.########", $culture)
$lonMax = $east.ToString("0.########", $culture)
$latitudeAtCenter = ($LatitudeMinimum + $LatitudeMaximum) / 2
$height = [Math]::Ceiling((($north - $south) * 110574) / $ResolutionMeters)
$width = [Math]::Ceiling((($east - $west) * 111320 * [Math]::Cos($latitudeAtCenter * [Math]::PI / 180)) / $ResolutionMeters)

# SoilGrids 2.0 coverage identifiers use wv0033 for water content at 33 kPa.
$properties = @("sand", "silt", "clay", "soc", "bdod", "cfvo", "wv0010", "wv0033", "wv1500")
$statistics = @("mean", "uncertainty")
$downloads = [System.Collections.Generic.List[object]]::new()

foreach ($property in $properties) {
    foreach ($statistic in $statistics) {
        $coverageId = "${property}_0-5cm_${statistic}"
        $url = "https://maps.isric.org/mapserv?map=/map/$property.map&SERVICE=WCS&VERSION=1.0.0&REQUEST=GetCoverage&COVERAGE=$coverageId&CRS=EPSG:4326&BBOX=$lonMin,$latMin,$lonMax,$latMax&WIDTH=$width&HEIGHT=$height&FORMAT=GEOTIFF_INT16"
        $fileName = "soilgrids_v2_0_${coverageId}.tif"
        $filePath = Join-Path $OutputDirectory $fileName

        Write-Host "Downloading $coverageId..."
        Invoke-WebRequest -Uri $url -OutFile $filePath
        if ((Get-Item -LiteralPath $filePath).Length -eq 0) {
            throw "SoilGrids returned an empty response for $coverageId."
        }

        $downloads.Add([ordered]@{ coverage_id = $coverageId; file = $fileName; request_url = $url })
        Start-Sleep -Milliseconds 250
    }
}

$manifest = [ordered]@{
    source = "ISRIC SoilGrids 2.0 WCS"
    downloaded_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    geographic_bounds = [ordered]@{
        latitude_minimum = $LatitudeMinimum
        latitude_maximum = $LatitudeMaximum
        longitude_minimum = $LongitudeMinimum
        longitude_maximum = $LongitudeMaximum
    }
    depth_interval = "0-5cm"
    requested_resolution_meters = $ResolutionMeters
    requested_output_width = $width
    requested_output_height = $height
    properties = $properties
    statistics = $statistics
    downloads = $downloads
    conditioning_applied = $false
    buffer_degrees = $BufferDegrees
    downloaded_bounds = @{ south = $south; north = $north; west = $west; east = $east }
    coverage_validation = "coverage_validation.json"
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $OutputDirectory "manifest.json") -Encoding utf8
Confirm-StaticDownload -ExpectedCount 18
Write-Host "Saved 18 raw SoilGrids WCS layers to: $OutputDirectory"
