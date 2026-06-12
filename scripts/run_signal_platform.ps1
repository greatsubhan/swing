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

$resolvedLog = if ([System.IO.Path]::IsPathRooted($LogFile)) { $LogFile } else { Join-Path $repoRoot $LogFile }
$logDir = Split-Path -Parent $resolvedLog
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

function Write-RunnerLog {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $resolvedLog -Value "[$timestamp] $Message" -Encoding utf8
}

function Build-ServeArguments {
    param(
        [string]$ServeConfig
    )

    $args = @("-u", "-m", "signal_platform", "--env-file", $EnvFile, "serve", "--config", $ServeConfig, "--poll-seconds", "$PollSeconds")
    if ($null -ne $MaxCycles) {
        $args += @("--max-cycles", "$MaxCycles")
    }
    if ($NoRunImmediately) {
        $args += "--no-run-immediately"
    }
    return $args
}

function Invoke-SignalPlatformOnce {
    param(
        [string]$ServeConfig
    )

    $arguments = Build-ServeArguments -ServeConfig $ServeConfig
    Write-RunnerLog "Starting: $PythonExe $($arguments -join ' ')"
    & $PythonExe @arguments *>> $resolvedLog
    $exitCode = $LASTEXITCODE
    Write-RunnerLog "ExitCode: $exitCode"
    return $exitCode
}

function Invoke-SignalPlatform {
    param(
        [string]$ServeConfig
    )

    $attempt = 0
    while ($true) {
        $attempt += 1
        Write-RunnerLog "Heartbeat: wrapper alive | attempt=$attempt | config=$ServeConfig"
        $exitCode = Invoke-SignalPlatformOnce -ServeConfig $ServeConfig

        if ($exitCode -eq 0) {
            if ($null -ne $MaxCycles -or $DryRun) {
                return
            }
            Write-RunnerLog "Serve process exited cleanly; restarting in 5 seconds to keep bots alive."
            Start-Sleep -Seconds 5
            continue
        }

        if ($null -ne $MaxCycles) {
            throw "Signal platform exited with code $exitCode"
        }

        Write-RunnerLog "Serve process crashed; restarting in 10 seconds."
        Start-Sleep -Seconds 10
    }
}

$serveConfig = $Config
if ($DryRun) {
    Write-Host "Running signal platform in dry-run mode"
    $tempConfig = Join-Path $repoRoot "platform.example.dryrun.json"
    $content = Get-Content $Config -Raw
    $content = $content -replace '"dispatch": "discord"', '"dispatch": "none"'
    Set-Content -Path $tempConfig -Value $content -Encoding utf8
    $serveConfig = $tempConfig
}

try {
    Invoke-SignalPlatform -ServeConfig $serveConfig
} finally {
    if ($DryRun -and (Test-Path $serveConfig) -and $serveConfig -like "*platform.example.dryrun.json") {
        Remove-Item $serveConfig -ErrorAction SilentlyContinue
    }
}
