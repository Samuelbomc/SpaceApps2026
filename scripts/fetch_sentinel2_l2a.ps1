[CmdletBinding()]
param(
    [double]$LatitudeMinimum = 5.4110,
    [double]$LatitudeMaximum = 6.5866,
    [double]$LongitudeMinimum = -75.5830,
    [double]$LongitudeMaximum = -74.6167,
    [string]$ClientId = $env:CDSE_CLIENT_ID,
    [string]$ClientSecret = $env:CDSE_CLIENT_SECRET,
    [int]$LookbackDays = 180,
    [double]$MaximumCatalogCloudCover = 70,
    [double]$TileSizeDegrees = 0.1,
    [int]$PixelSizeMeters = 10,
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"

if ($LatitudeMinimum -lt -90 -or $LatitudeMaximum -gt 90 -or $LatitudeMinimum -ge $LatitudeMaximum) {
    throw "LatitudeMinimum and LatitudeMaximum must be ordered values between -90 and 90."
}
if ($LongitudeMinimum -lt -180 -or $LongitudeMaximum -gt 180 -or $LongitudeMinimum -ge $LongitudeMaximum) {
    throw "LongitudeMinimum and LongitudeMaximum must be ordered values between -180 and 180."
}
if ([string]::IsNullOrWhiteSpace($ClientId) -or [string]::IsNullOrWhiteSpace($ClientSecret)) {
    throw "Set CDSE_CLIENT_ID and CDSE_CLIENT_SECRET or pass -ClientId and -ClientSecret. Create a Copernicus Data Space OAuth client before running this script."
}
if ($LookbackDays -lt 1 -or $TileSizeDegrees -le 0 -or $PixelSizeMeters -lt 1) {
    throw "LookbackDays, TileSizeDegrees, and PixelSizeMeters must be positive."
}

function Get-CDSEAccessToken {
    param([string]$Id, [string]$Secret)
    $tokenResponse = Invoke-RestMethod `
        -Uri "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token" `
        -Method Post `
        -ContentType "application/x-www-form-urlencoded" `
        -Body @{ client_id = $Id; client_secret = $Secret; grant_type = "client_credentials" }
    return $tokenResponse.access_token
}

function Get-SentinelTiles {
    param(
        [double]$South,
        [double]$North,
        [double]$West,
        [double]$East,
        [double]$Step
    )

    $tiles = [System.Collections.Generic.List[object]]::new()
    $row = 0
    for ($tileSouth = $South; $tileSouth -lt $North; $tileSouth += $Step) {
        $tileNorth = [Math]::Min($tileSouth + $Step, $North)
        $column = 0
        for ($tileWest = $West; $tileWest -lt $East; $tileWest += $Step) {
            $tileEast = [Math]::Min($tileWest + $Step, $East)
            $tiles.Add([ordered]@{
                row = $row
                column = $column
                south = [Math]::Round($tileSouth, 8)
                north = [Math]::Round($tileNorth, 8)
                west = [Math]::Round($tileWest, 8)
                east = [Math]::Round($tileEast, 8)
            })
            $column++
        }
        $row++
    }
    return $tiles
}

$now = (Get-Date).ToUniversalTime()
$catalogFrom = $now.AddDays(-$LookbackDays)
$accessToken = Get-CDSEAccessToken -Id $ClientId -Secret $ClientSecret
$headers = @{ Authorization = "Bearer $accessToken" }
$bbox = @($LongitudeMinimum, $LatitudeMinimum, $LongitudeMaximum, $LatitudeMaximum)

$catalogRequest = [ordered]@{
    bbox = $bbox
    datetime = "$($catalogFrom.ToString('o'))/$($now.ToString('o'))"
    collections = @("sentinel-2-l2a")
    limit = 100
}

Write-Host "Searching Copernicus Data Space for Sentinel-2 L2A candidates..."
$catalogResponse = Invoke-RestMethod `
    -Uri "https://sh.dataspace.copernicus.eu/catalog/v1/search" `
    -Method Post `
    -Headers $headers `
    -ContentType "application/json" `
    -Body ($catalogRequest | ConvertTo-Json -Depth 8)

$candidates = @($catalogResponse.features) | Where-Object {
    $null -ne $_.properties.datetime -and
    $null -ne $_.properties.'eo:cloud_cover' -and
    [double]$_.properties.'eo:cloud_cover' -le $MaximumCatalogCloudCover
} | Sort-Object { [datetimeoffset]$_.properties.datetime } -Descending

if ($candidates.Count -eq 0) {
    throw "No Sentinel-2 L2A scene met the catalog cloud-cover threshold. Increase -MaximumCatalogCloudCover or -LookbackDays."
}

$scene = $candidates[0]
$sceneTimestamp = ([datetimeoffset]$scene.properties.datetime).ToUniversalTime()
$sceneDayStart = $sceneTimestamp.UtcDateTime.Date
$sceneDayEnd = $sceneDayStart.AddDays(1).AddTicks(-1)
$downloadTimestamp = $now.ToString("yyyyMMdd_HHmmssZ")
$sceneName = $sceneTimestamp.ToString("yyyyMMddTHHmmssZ")
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $PSScriptRoot "..\SENTINEL2\SENTINEL2_L2A_${sceneName}_${downloadTimestamp}"
}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path
$archiveDirectory = Join-Path $OutputDirectory "raw_process_responses"
New-Item -ItemType Directory -Force -Path $archiveDirectory | Out-Null

$tar = Get-Command tar.exe -ErrorAction SilentlyContinue
if ($null -eq $tar) { $tar = Get-Command tar -ErrorAction SilentlyContinue }
if ($null -eq $tar) {
    throw "tar was not found. Install a TAR-compatible extractor before running the Sentinel-2 script."
}

$evalscript = @'
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B04", "B08", "SCL"], units: "DN" }],
    output: [
      { id: "B04", bands: 1, sampleType: "UINT16" },
      { id: "B08", bands: 1, sampleType: "UINT16" },
      { id: "SCL", bands: 1, sampleType: "UINT8" }
    ]
  };
}
function evaluatePixel(sample) {
  return { B04: [sample.B04], B08: [sample.B08], SCL: [sample.SCL] };
}
'@

$tiles = Get-SentinelTiles -South $LatitudeMinimum -North $LatitudeMaximum -West $LongitudeMinimum -East $LongitudeMaximum -Step $TileSizeDegrees
$manifestTiles = [System.Collections.Generic.List[object]]::new()

foreach ($tile in $tiles) {
    $latitudeAtCenter = ($tile.south + $tile.north) / 2
    $height = [Math]::Ceiling((($tile.north - $tile.south) * 111320) / $PixelSizeMeters)
    $width = [Math]::Ceiling((($tile.east - $tile.west) * 111320 * [Math]::Cos($latitudeAtCenter * [Math]::PI / 180)) / $PixelSizeMeters)
    $tileId = "r{0:D2}_c{1:D2}" -f $tile.row, $tile.column
    $tilePayload = [ordered]@{
        input = [ordered]@{
            bounds = [ordered]@{
                bbox = @($tile.west, $tile.south, $tile.east, $tile.north)
                properties = @{ crs = "http://www.opengis.net/def/crs/OGC/1.3/CRS84" }
            }
            data = @([ordered]@{
                type = "sentinel-2-l2a"
                dataFilter = [ordered]@{
                    timeRange = @{ from = $sceneDayStart.ToString("yyyy-MM-ddTHH:mm:ssZ"); to = $sceneDayEnd.ToString("yyyy-MM-ddTHH:mm:ssZ") }
                    maxCloudCoverage = $MaximumCatalogCloudCover
                    mosaickingOrder = "leastCC"
                }
                processing = @{ upsampling = "NEAREST"; downsampling = "NEAREST" }
            })
        }
        output = [ordered]@{
            width = $width
            height = $height
            responses = @(
                @{ identifier = "B04"; format = @{ type = "image/tiff" } },
                @{ identifier = "B08"; format = @{ type = "image/tiff" } },
                @{ identifier = "SCL"; format = @{ type = "image/tiff" } }
            )
        }
        evalscript = $evalscript
    }

    $tarPath = Join-Path $archiveDirectory "sentinel2_l2a_${sceneName}_${tileId}.tar"
    $extractDirectory = Join-Path $archiveDirectory "extract_${tileId}"
    New-Item -ItemType Directory -Force -Path $extractDirectory | Out-Null

    Write-Host "Downloading $tileId ($width x $height pixels)..."
    Invoke-WebRequest `
        -Uri "https://sh.dataspace.copernicus.eu/api/v1/process" `
        -Method Post `
        -Headers @{ Authorization = "Bearer $accessToken"; Accept = "application/tar" } `
        -ContentType "application/json" `
        -Body ($tilePayload | ConvertTo-Json -Depth 12 -Compress) `
        -OutFile $tarPath
    if ((Get-Item -LiteralPath $tarPath).Length -eq 0) {
        throw "The Process API returned an empty archive for $tileId."
    }

    & $tar.Source "-xf" $tarPath "-C" $extractDirectory
    if ($LASTEXITCODE -ne 0) { throw "Could not extract $tarPath." }

    $bandFiles = @{}
    foreach ($band in @("B04", "B08", "SCL")) {
        $match = Get-ChildItem -LiteralPath $extractDirectory -Recurse -File | Where-Object {
            $_.Extension -in ".tif", ".tiff" -and $_.BaseName -match "(?i)$band"
        } | Select-Object -First 1
        if ($null -eq $match) { throw "The Process API archive for $tileId did not contain $band." }
        $targetName = "sentinel2_l2a_${sceneName}_${tileId}_${band}_10m.tif"
        Move-Item -LiteralPath $match.FullName -Destination (Join-Path $OutputDirectory $targetName)
        $bandFiles[$band] = $targetName
    }

    $manifestTiles.Add([ordered]@{
        id = $tileId
        bounds = $tile
        output_width = $width
        output_height = $height
        bands = $bandFiles
        raw_process_response = (Split-Path -Leaf $tarPath)
    })
    Start-Sleep -Milliseconds 200
}

$manifest = [ordered]@{
    source = "Copernicus Data Space Sentinel Hub Process API"
    downloaded_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    geographic_bounds = [ordered]@{
        latitude_minimum = $LatitudeMinimum
        latitude_maximum = $LatitudeMaximum
        longitude_minimum = $LongitudeMinimum
        longitude_maximum = $LongitudeMaximum
    }
    selected_catalog_scene = [ordered]@{
        id = $scene.id
        acquisition_datetime_utc = $sceneTimestamp.ToString("o")
        catalog_cloud_cover_percent = $scene.properties.'eo:cloud_cover'
        mgrs_tile = $scene.properties.'s2:mgrs_tile'
    }
    requested_bands = @("B04", "B08", "SCL")
    requested_pixel_size_meters = $PixelSizeMeters
    scl_resampling = "The Process API returns SCL on the same 10 m output grid as B04 and B08. Use SCL later to mask cloud and shadow classes before calculating NDVI."
    catalog_cloud_cover_threshold_percent = $MaximumCatalogCloudCover
    tiles = $manifestTiles
    conditioning_applied = $false
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $OutputDirectory "manifest.json") -Encoding utf8
Write-Host "Saved Sentinel-2 B04, B08, and SCL tiles to: $OutputDirectory"
