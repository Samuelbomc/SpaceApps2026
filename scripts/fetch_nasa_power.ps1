[CmdletBinding()]
param(
    [double]$LatitudeMinimum = 5.4110,
    [double]$LatitudeMaximum = 6.5866,
    [double]$LongitudeMinimum = -75.5830,
    [double]$LongitudeMaximum = -74.6167,
    [double]$GridSpacingDegrees = 0.5,
    [int]$Years = 15,
    [datetime]$EndDate = ((Get-Date).ToUniversalTime().Date.AddDays(-1)),
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"

if ($LatitudeMinimum -lt -90 -or $LatitudeMaximum -gt 90 -or $LatitudeMinimum -ge $LatitudeMaximum) {
    throw "LatitudeMinimum and LatitudeMaximum must be ordered values between -90 and 90."
}

if ($LongitudeMinimum -lt -180 -or $LongitudeMaximum -gt 180 -or $LongitudeMinimum -ge $LongitudeMaximum) {
    throw "LongitudeMinimum and LongitudeMaximum must be ordered values between -180 and 180."
}

if ($Years -lt 1) {
    throw "Years must be at least 1."
}

if ($GridSpacingDegrees -le 0) {
    throw "GridSpacingDegrees must be greater than zero."
}

# The interval is inclusive: 15 full years ending on the last complete UTC day.
$EndDate = $EndDate.Date
$StartDate = $EndDate.AddYears(-$Years).AddDays(1)

# These are the NASA POWER variables required by the three weekly time-series
# models before any conditioning or feature engineering.
$Parameters = @(
    "T2M",                    # Temperature at 2 m
    "T2M_MIN",                # Daily minimum temperature at 2 m
    "T2M_MAX",                # Daily maximum temperature at 2 m
    "RH2M",                   # Relative humidity at 2 m
    "QV2M",                   # Specific humidity at 2 m
    "WS2M",                   # Wind speed at 2 m
    "ALLSKY_SFC_SW_DWN"       # All-sky surface shortwave downward irradiance
)

$Culture = [System.Globalization.CultureInfo]::InvariantCulture
$LatMinText = $LatitudeMinimum.ToString("0.####", $Culture)
$LatMaxText = $LatitudeMaximum.ToString("0.####", $Culture)
$LonMinText = $LongitudeMinimum.ToString("0.####", $Culture)
$LonMaxText = $LongitudeMaximum.ToString("0.####", $Culture)
$StartText = $StartDate.ToString("yyyyMMdd", $Culture)
$EndText = $EndDate.ToString("yyyyMMdd", $Culture)

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $PSScriptRoot "..\POWER\POWER_DAILY_AG_${StartText}_${EndText}_UTC"
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path

function Get-GridCenters {
    param([double]$Minimum, [double]$Maximum, [double]$Spacing)

    $first = [Math]::Round($Minimum / $Spacing, 0, [System.MidpointRounding]::AwayFromZero) * $Spacing
    if ($first -lt $Minimum) { $first += $Spacing }

    $values = [System.Collections.Generic.List[double]]::new()
    for ($value = $first; $value -le $Maximum + 0.000001; $value += $Spacing) {
        $values.Add([Math]::Round($value, 6))
    }
    if (($Maximum - $values[$values.Count - 1]) -gt ($Spacing / 2)) {
        $values.Add($Maximum)
    }
    return $values
}

$Latitudes = Get-GridCenters -Minimum $LatitudeMinimum -Maximum $LatitudeMaximum -Spacing $GridSpacingDegrees
$Longitudes = Get-GridCenters -Minimum $LongitudeMinimum -Maximum $LongitudeMaximum -Spacing $GridSpacingDegrees
$Files = [System.Collections.Generic.List[string]]::new()
$Requests = [System.Collections.Generic.List[string]]::new()
$GridPoints = [System.Collections.Generic.List[object]]::new()

foreach ($Latitude in $Latitudes) {
    foreach ($Longitude in $Longitudes) {
        $LatitudeText = $Latitude.ToString("0.####", $Culture)
        $LongitudeText = $Longitude.ToString("0.####", $Culture)
        $Query = @{
            parameters = ($Parameters -join ",")
            community = "AG"
            longitude = $LongitudeText
            latitude = $LatitudeText
            start = $StartText
            end = $EndText
            format = "CSV"
            'time-standard' = "UTC"
        }

        $QueryString = ($Query.GetEnumerator() | ForEach-Object {
            "{0}={1}" -f [uri]::EscapeDataString($_.Key), [uri]::EscapeDataString([string]$_.Value)
        }) -join "&"
        $RequestUrl = "https://power.larc.nasa.gov/api/temporal/daily/point?$QueryString"
        $FileName = "nasa_power_daily_raw_${StartText}_${EndText}_lat${LatitudeText}_lon${LongitudeText}_UTC.csv"
        $CsvPath = Join-Path $OutputDirectory $FileName

        if (Test-Path -LiteralPath $CsvPath -PathType Leaf) {
            if ((Get-Item -LiteralPath $CsvPath).Length -eq 0) {
                Remove-Item -LiteralPath $CsvPath -Force
            }
        }

        if (-not (Test-Path -LiteralPath $CsvPath -PathType Leaf)) {
            Write-Host "Downloading latitude $LatitudeText, longitude $LongitudeText..."
            Invoke-WebRequest -Uri $RequestUrl -OutFile $CsvPath
            Start-Sleep -Seconds 1
        }
        else {
            Write-Host "Using existing latitude $LatitudeText, longitude $LongitudeText response..."
        }

        if ((Get-Item -LiteralPath $CsvPath).Length -eq 0) {
            throw "NASA POWER returned an empty file for latitude $LatitudeText, longitude $LongitudeText."
        }

        $Files.Add($FileName)
        $Requests.Add($RequestUrl)
        $GridPoints.Add([ordered]@{ latitude = $Latitude; longitude = $Longitude })
    }
}

$Manifest = [ordered]@{
    source = "NASA POWER Daily Point API"
    endpoint = "https://power.larc.nasa.gov/api/temporal/daily/point"
    downloaded_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    geographic_bounds = [ordered]@{
        latitude_minimum = $LatitudeMinimum
        latitude_maximum = $LatitudeMaximum
        longitude_minimum = $LongitudeMinimum
        longitude_maximum = $LongitudeMaximum
    }
    time_standard = "UTC"
    start_date = $StartDate.ToString("yyyy-MM-dd")
    end_date = $EndDate.ToString("yyyy-MM-dd")
    included_days = ($EndDate - $StartDate).Days + 1
    parameters = $Parameters
    grid_spacing_degrees = $GridSpacingDegrees
    grid_points = $GridPoints
    requests = $Requests
    files = $Files
    conditioning_applied = $false
}

$ManifestPath = Join-Path $OutputDirectory "manifest.json"
$Manifest | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $ManifestPath -Encoding utf8

Write-Host "Saved $($Files.Count) raw API responses to: $OutputDirectory"
Write-Host "Saved request metadata: $ManifestPath"
