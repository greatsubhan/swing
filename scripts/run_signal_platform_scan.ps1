param(
    [string]$Strategy = "",
    [string]$Config = "config/platform.example.json",
    [string]$EnvFile = ".env",
    [string]$PythonExe = "",
    [string]$LogFile = "logs/signal_platform_scan.log",
    [string]$Watchlist = "",
    [string]$Granularity = "",
    [string]$HigherTimeframe = "",
    [string]$OutputDir = "",
    [string]$Dispatch = "",
    [double]$CatchUpHours = -1
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    try {
        $PythonExe = (& py -3 -c "import sys; print(sys.executable)").Trim()
    } catch {
        $PythonExe = "python"
    }
}

$logPath = if ([System.IO.Path]::IsPathRooted($LogFile)) { $LogFile } else { Join-Path $repoRoot $LogFile }
$logDir = Split-Path -Parent $logPath
if ($logDir) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

$arguments = @(
    "-m", "signal_platform",
    "--env-file", $EnvFile,
    "scan-route",
    "--config", $Config,
    "--strategy", $Strategy
)

if (-not [string]::IsNullOrWhiteSpace($Watchlist)) {
    $arguments += @("--watchlist", $Watchlist)
}
if (-not [string]::IsNullOrWhiteSpace($Granularity)) {
    $arguments += @("--granularity", $Granularity)
}
if (-not [string]::IsNullOrWhiteSpace($HigherTimeframe)) {
    $arguments += @("--higher-timeframe", $HigherTimeframe)
}
if (-not [string]::IsNullOrWhiteSpace($OutputDir)) {
    $arguments += @("--out", $OutputDir)
}
if (-not [string]::IsNullOrWhiteSpace($Dispatch)) {
    $arguments += @("--dispatch", $Dispatch)
}
if ($CatchUpHours -ge 0) {
    $arguments += @("--catch-up-hours", $CatchUpHours.ToString([System.Globalization.CultureInfo]::InvariantCulture))
}

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "[$timestamp] Starting: $PythonExe $($arguments -join ' ')" -Encoding utf8
$commandOutput = & $PythonExe @Arguments 2>&1
$commandOutput | Out-String | Add-Content -Path $logPath -Encoding utf8
$exitCode = $LASTEXITCODE
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "[$timestamp] ExitCode: $exitCode" -Encoding utf8
if ($exitCode -ne 0) {
    throw "Signal platform scan exited with code $exitCode"
}

try {
    $parsed = $commandOutput | Out-String | ConvertFrom-Json
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logPath -Value "[$timestamp] Summary: strategy=$($parsed.strategy_id) dispatch=$($parsed.dispatch) catch_up_hours=$($parsed.catch_up_hours) signals_found=$($parsed.signals_found) fresh=$($parsed.fresh_signals) recovered=$($parsed.recovered_entries_found) outcomes_sent=$($parsed.outcomes_sent)" -Encoding utf8
} catch {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logPath -Value "[$timestamp] Summary: unable to parse JSON output" -Encoding utf8
}
