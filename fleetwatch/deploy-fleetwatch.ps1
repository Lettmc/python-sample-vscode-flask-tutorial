#Requires -Version 5.1
<#
.SYNOPSIS
    FleetWatcher AI — One-click deployment script for AXIS P3268-LVE (and any AXIS camera).
.DESCRIPTION
    1. Verifies camera connectivity via VAPIX
    2. Reads device info (serial, model, firmware)
    3. Creates/verifies AOA scenarios
    4. Writes all FleetWatcher files to a local staging folder
    5. Walks you through the 4 FixedIT UI upload steps with browser opens
.NOTES
    Run from PowerShell as Administrator from the fleetwatch\ directory.
    Requirements: PowerShell 5.1+, curl (built-in on Win10+)
#>

param(
    [string]$CameraHost  = "192.168.5.201",
    [string]$Username    = "hermes",
    [string]$Password    = "",        # prompt if empty
    [string]$CloudUrl    = "",        # FW_CLOUD_URL — your Render backend URL
    [string]$CloudToken  = "",        # FW_CLOUD_TOKEN — from Render dashboard
    [string]$Site        = "Axis Experience Center",
    [string]$Area        = "Zone 1"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$FW_VERSION = "1.0.0"
$STAGING    = "$env:USERPROFILE\Desktop\FleetWatcher-Deploy"
$BASE_URL   = "https://$CameraHost"
$AOA_CGI    = "/local/objectanalytics/control.cgi"

# ── Color helpers ──────────────────────────────────────────────────────────────
function Write-Step  { param($msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-OK    { param($msg) Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "    [!!] $msg" -ForegroundColor Yellow }
function Write-Fail  { param($msg) Write-Host "    [XX] $msg" -ForegroundColor Red }

# ── Credential prompt ──────────────────────────────────────────────────────────
if (-not $Password) {
    $secPass  = Read-Host "Camera password for '$Username'" -AsSecureString
    $BSTR     = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secPass)
    $Password = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
}

$Cred = [System.Convert]::ToBase64String(
    [System.Text.Encoding]::ASCII.GetBytes("${Username}:${Password}")
)

# ── VAPIX helper ───────────────────────────────────────────────────────────────
function Vapix-Post {
    param([string]$Path, [string]$Body)
    try {
        $resp = Invoke-RestMethod `
            -Uri        "$BASE_URL$Path" `
            -Method     POST `
            -Headers    @{ Authorization = "Basic $Cred"; "Content-Type" = "application/json" } `
            -Body       $Body `
            -SkipCertificateCheck `
            -TimeoutSec 10
        return $resp
    } catch {
        return $null
    }
}

function Vapix-Get {
    param([string]$Path)
    try {
        $resp = Invoke-RestMethod `
            -Uri     "$BASE_URL$Path" `
            -Method  GET `
            -Headers @{ Authorization = "Basic $Cred" } `
            -SkipCertificateCheck `
            -TimeoutSec 8
        return $resp
    } catch {
        return $null
    }
}

# ══════════════════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "  ███████╗██╗     ███████╗███████╗████████╗" -ForegroundColor Blue
Write-Host "  ██╔════╝██║     ██╔════╝██╔════╝╚══██╔══╝" -ForegroundColor Blue
Write-Host "  █████╗  ██║     █████╗  █████╗     ██║   " -ForegroundColor Blue
Write-Host "  ██╔══╝  ██║     ██╔══╝  ██╔══╝     ██║   " -ForegroundColor Blue
Write-Host "  ██║     ███████╗███████╗███████╗    ██║   " -ForegroundColor Blue
Write-Host "  ╚═╝     ╚══════╝╚══════╝╚══════╝    ╚═╝   " -ForegroundColor Blue
Write-Host "  WATCHER AI — Deployment Script v$FW_VERSION" -ForegroundColor White
Write-Host "  Target: $CameraHost | Site: $Site" -ForegroundColor DarkGray
Write-Host ""

# ── Step 1: Camera connectivity ────────────────────────────────────────────────
Write-Step "Testing camera connectivity..."
$devInfo = Vapix-Post "/axis-cgi/basicdeviceinfo.cgi" '{"apiVersion":"1.0","method":"getAllProperties"}'

if (-not $devInfo) {
    Write-Fail "Cannot reach $CameraHost — check IP and credentials"
    exit 1
}

$props  = $devInfo.data.propertyList
$SERIAL  = $props.SerialNumber
$MODEL   = $props.Model
$FW_VER  = $props.Version
$ARCH    = $props.Architecture

Write-OK "Connected to: $MODEL (S/N: $SERIAL)"
Write-OK "Firmware: $FW_VER | Arch: $ARCH"

# ── Step 2: Check AOA availability ────────────────────────────────────────────
Write-Step "Checking AXIS Object Analytics..."
$aoaConfig = Vapix-Post $AOA_CGI '{"apiVersion":"1.2","context":"fleetwatch","method":"getConfiguration"}'

if (-not $aoaConfig -or $aoaConfig.error) {
    Write-Warn "AOA not responding — may not be installed or licensed on this camera"
    Write-Warn "Install it from: https://$CameraHost/#settings/apps"
    $aoaAvailable = $false
} else {
    $existingScenarios = $aoaConfig.data.scenarios
    Write-OK "AOA active — found $($existingScenarios.Count) existing scenario(s)"
    $aoaAvailable = $true
}

# ── Step 3: Create AOA scenarios if needed ────────────────────────────────────
if ($aoaAvailable) {
    Write-Step "Configuring AOA scenarios for FleetWatcher..."

    $scenarioTypes = @(
        @{ type="motion";          name="FW Motion Detection";       trigger="all" },
        @{ type="timeInArea";      name="FW Time In Area (Dwell)";   trigger="human" },
        @{ type="crosslinecounting"; name="FW Line Crossing";        trigger="all" },
        @{ type="occupancyInArea"; name="FW Occupancy Monitor";      trigger="human" }
    )

    foreach ($s in $scenarioTypes) {
        $exists = $existingScenarios | Where-Object { $_.name -eq $s.name }
        if ($exists) {
            Write-OK "Scenario already exists: '$($s.name)'"
            continue
        }
        $body = @{
            apiVersion = "1.2"
            context    = "fleetwatch"
            method     = "addScenario"
            params     = @{
                name    = $s.name
                type    = $s.type
                filters = @(@{ type="objectClassifications"; objectClassifications=@("human","vehicle") })
            }
        } | ConvertTo-Json -Depth 10

        $result = Vapix-Post $AOA_CGI $body
        if ($result -and -not $result.error) {
            Write-OK "Created scenario: '$($s.name)'"
        } else {
            Write-Warn "Could not auto-create '$($s.name)' — add manually at https://$CameraHost/local/objectanalytics/"
        }
    }
}

# ── Step 4: Create staging directory with all FleetWatcher files ──────────────
Write-Step "Writing FleetWatcher files to staging folder..."
New-Item -ItemType Directory -Force -Path $STAGING | Out-Null
New-Item -ItemType Directory -Force -Path "$STAGING\helper_files" | Out-Null
New-Item -ItemType Directory -Force -Path "$STAGING\configs" | Out-Null

# ── Helper: write a file to staging ───────────────────────────────────────────
function Write-StagingFile {
    param([string]$SubDir, [string]$Name, [string]$Content)
    $path = "$STAGING\$SubDir\$Name"
    [System.IO.File]::WriteAllText($path, $Content, [System.Text.Encoding]::UTF8)
    Write-OK "Staged: $SubDir\$Name"
}

# ── Detect script directory and read source files ──────────────────────────────
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) { $ScriptDir = Get-Location }

$sourceFiles = @{
    "helper_files\fleetwatch_logic.star"          = "fleetwatch_logic.star"
    "helper_files\clip_upload.sh"                 = "clip_upload.sh"
    "helper_files\health_check.sh"                = "health_check.sh"
    "helper_files\poll_aoa.sh"                    = "poll_aoa.sh"
    "helper_files\scene_metadata_reader.sh"       = "scene_metadata_reader.sh"
    "configs\config_agent.conf"                   = "config_agent.conf"
    "configs\config_input_aoa_events.conf"        = "config_input_aoa_events.conf"
    "configs\config_input_camera_health.conf"     = "config_input_camera_health.conf"
    "configs\config_input_scene_metadata.conf"    = "config_input_scene_metadata.conf"
    "configs\config_process_fleetwatch.conf"      = "config_process_fleetwatch.conf"
    "configs\config_output_local_log.conf"        = "config_output_local_log.conf"
    "configs\config_output_https_push.conf"       = "config_output_https_push.conf"
    "ui\index.html"                               = "index.html"
}

New-Item -ItemType Directory -Force -Path "$STAGING\ui" | Out-Null

foreach ($dest in $sourceFiles.Keys) {
    $srcName = $sourceFiles[$dest]
    $srcPath = Join-Path $ScriptDir $srcName
    if (Test-Path $srcPath) {
        $content = Get-Content $srcPath -Raw -Encoding UTF8
        $fullDest = Join-Path $STAGING $dest
        $dir = Split-Path $fullDest -Parent
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        [System.IO.File]::WriteAllText($fullDest, $content, [System.Text.Encoding]::UTF8)
        Write-OK "Staged: $dest"
    } else {
        Write-Warn "Source not found: $srcPath (skip)"
    }
}

# Write environment variable reference file
$envContent = @"
# FleetWatcher AI — FixedIT Environment Variables
# Copy-paste these into the FixedIT Data Agent > Environment tab

VAPIX_USERNAME=$Username
VAPIX_PASSWORD=$Password
SITE=$Site
AREA=$Area
DEVICE_PROP_SERIAL=$SERIAL
AOA_POLL_INTERVAL=5s
SYNC_INTERVAL_SECONDS=10
FLUSH_INTERVAL_SECONDS=10

# Set these after deploying the Render backend:
# FW_CLOUD_URL=https://your-service.onrender.com/functions/v1/fw-clip
# FW_CLOUD_TOKEN=your-render-generated-token
"@
[System.IO.File]::WriteAllText("$STAGING\ENVIRONMENT_VARS.txt", $envContent, [System.Text.Encoding]::UTF8)
Write-OK "Staged: ENVIRONMENT_VARS.txt"

# ── Step 5: Open FixedIT UI with instructions ──────────────────────────────────
Write-Host ""
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  STAGING COMPLETE — Files ready at:" -ForegroundColor White
Write-Host "  $STAGING" -ForegroundColor Yellow
Write-Host ""
Write-Host "  NOW FOLLOW THESE 4 STEPS IN THE FIXEDIT UI:" -ForegroundColor White
Write-Host ""
Write-Host "  STEP 1 — Helper Files" -ForegroundColor Green
Write-Host "    Upload ALL files from: $STAGING\helper_files\" -ForegroundColor Gray
Write-Host "    (5 files: .star + 4x .sh)"
Write-Host ""
Write-Host "  STEP 2 — Configs (in this exact order)" -ForegroundColor Green
Write-Host "    1. config_agent.conf"
Write-Host "    2. config_input_aoa_events.conf"
Write-Host "    3. config_input_camera_health.conf"
Write-Host "    4. config_input_scene_metadata.conf"
Write-Host "    5. config_process_fleetwatch.conf"
Write-Host "    6. config_output_local_log.conf"
Write-Host "    7. config_output_https_push.conf  (only if cloud URL is set)"
Write-Host "    Upload ALL from: $STAGING\configs\" -ForegroundColor Gray
Write-Host ""
Write-Host "  STEP 3 — Environment Variables" -ForegroundColor Green
Write-Host "    Copy from: $STAGING\ENVIRONMENT_VARS.txt" -ForegroundColor Gray
Write-Host ""
Write-Host "  STEP 4 — Custom UI" -ForegroundColor Green
Write-Host "    Upload: $STAGING\ui\index.html" -ForegroundColor Gray
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Open FixedIT in browser
$choice = Read-Host "Open FixedIT Data Agent in browser now? (Y/n)"
if ($choice -ne 'n') {
    Start-Process "https://$CameraHost/local/FixeditDataAgent/index.html"
}

# Open staging folder
Start-Process explorer.exe $STAGING

Write-Host ""
Write-Host "  Camera: $MODEL S/N:$SERIAL @ $CameraHost" -ForegroundColor DarkGray
Write-Host "  After upload, FleetWatcher UI: https://$CameraHost/local/FixeditDataAgent/index.html#/custom-ui" -ForegroundColor Cyan
Write-Host ""
