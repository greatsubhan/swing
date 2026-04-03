param(
    [string]$Config = "config/platform.example.json",
    [int]$PollSeconds = 30,
    [string]$EnvFile = ".env",
    [string]$PythonExe = "",
    [string]$LogFile = "logs/signal_platform.log",
    [Nullable[int]]$MaxCycles = $null,
    [switch]$NoRunImmediately,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
$logPath = Join-Path $repoRoot $LogFile
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

function Invoke-SignalPlatform {
    param(
        [string[]]$Arguments
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logPath -Value "[$timestamp] Starting: $PythonExe $($Arguments -join ' ')"
    & $PythonExe @Arguments *>> $logPath
    $exitCode = $LASTEXITCODE
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logPath -Value "[$timestamp] ExitCode: $exitCode"
    if ($exitCode -ne 0) {
        throw "Signal platform exited with code $exitCode"
    }
}

if ($DryRun) {
    Write-Host "Running signal platform in dry-run mode"
    $tempConfig = Join-Path $repoRoot "platform.example.dryrun.json"
    $content = Get-Content $Config -Raw
    $content = $content -replace '"dispatch": "discord"', '"dispatch": "none"'
    Set-Content -Path $tempConfig -Value $content
    if ($null -ne $MaxCycles) {
        if ($NoRunImmediately) {
            Invoke-SignalPlatform -Arguments @("-m", "signal_platform", "--env-file", $EnvFile, "serve", "--config", $tempConfig, "--poll-seconds", "$PollSeconds", "--max-cycles", "$MaxCycles", "--no-run-immediately")
        } else {
            Invoke-SignalPlatform -Arguments @("-m", "signal_platform", "--env-file", $EnvFile, "serve", "--config", $tempConfig, "--poll-seconds", "$PollSeconds", "--max-cycles", "$MaxCycles")
        }
    } else {
        if ($NoRunImmediately) {
            Invoke-SignalPlatform -Arguments @("-m", "signal_platform", "--env-file", $EnvFile, "serve", "--config", $tempConfig, "--poll-seconds", "$PollSeconds", "--no-run-immediately")
        } else {
            Invoke-SignalPlatform -Arguments @("-m", "signal_platform", "--env-file", $EnvFile, "serve", "--config", $tempConfig, "--poll-seconds", "$PollSeconds")
        }
    }
    Remove-Item $tempConfig -ErrorAction SilentlyContinue
} else {
    if ($null -ne $MaxCycles) {
        if ($NoRunImmediately) {
            Invoke-SignalPlatform -Arguments @("-m", "signal_platform", "--env-file", $EnvFile, "serve", "--config", $Config, "--poll-seconds", "$PollSeconds", "--max-cycles", "$MaxCycles", "--no-run-immediately")
        } else {
            Invoke-SignalPlatform -Arguments @("-m", "signal_platform", "--env-file", $EnvFile, "serve", "--config", $Config, "--poll-seconds", "$PollSeconds", "--max-cycles", "$MaxCycles")
        }
    } else {
        if ($NoRunImmediately) {
            Invoke-SignalPlatform -Arguments @("-m", "signal_platform", "--env-file", $EnvFile, "serve", "--config", $Config, "--poll-seconds", "$PollSeconds", "--no-run-immediately")
        } else {
            Invoke-SignalPlatform -Arguments @("-m", "signal_platform", "--env-file", $EnvFile, "serve", "--config", $Config, "--poll-seconds", "$PollSeconds")
        }
    }
}
