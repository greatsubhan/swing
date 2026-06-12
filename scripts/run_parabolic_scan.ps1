param(
    [string]$Profile = "NAS100_PARABOLIC_PAPER",
    [string]$Provider = "oanda",
    [string]$EnvFile = "parabolic-exhaustion-bot\.env",
    [string]$PythonExe = "",
    [string]$LogFile = "logs\parabolic_scan.log"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$botRoot = Join-Path $repoRoot "parabolic-exhaustion-bot"
Set-Location $botRoot

$logPath = if ([System.IO.Path]::IsPathRooted($LogFile)) { $LogFile } else { Join-Path $repoRoot $LogFile }
$logDir = Split-Path -Parent $logPath
if ($logDir) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    try {
        $PythonExe = (& py -3 -c "import sys; print(sys.executable)").Trim()
    } catch {
        $PythonExe = "python"
    }
}

$resolvedEnv = if ([System.IO.Path]::IsPathRooted($EnvFile)) { $EnvFile } else { Join-Path $repoRoot $EnvFile }
$srcPath = Join-Path $botRoot "src"
if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = $srcPath
} else {
    $env:PYTHONPATH = "$srcPath;$($env:PYTHONPATH)"
}

$arguments = @(
    "-m", "parabolic_exhaustion.live.scan",
    "--profile", $Profile,
    "--provider", $Provider,
    "--env-file", $resolvedEnv
)

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "[$timestamp] Starting: $PythonExe $($arguments -join ' ')"
& $PythonExe @arguments *>> $logPath
$exitCode = $LASTEXITCODE
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "[$timestamp] ExitCode: $exitCode"
if ($exitCode -ne 0) {
    throw "Parabolic scan exited with code $exitCode"
}
