param(
    [string]$Config = "config/platform.example.json",
    [string]$EnvFile = ".env",
    [int]$PollSeconds = 30,
    [string]$LogFile = "logs/signal_platform.log",
    [string]$CommandBotLogFile = "logs/signal_platform_command_bot.log",
    [string]$PythonExe = "",
    [switch]$StatusOnly,
    [switch]$Quiet
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

$resolvedConfig = if ([System.IO.Path]::IsPathRooted($Config)) { $Config } else { Join-Path $repoRoot $Config }
$resolvedEnv = if ([System.IO.Path]::IsPathRooted($EnvFile)) { $EnvFile } else { Join-Path $repoRoot $EnvFile }
$resolvedLog = if ([System.IO.Path]::IsPathRooted($LogFile)) { $LogFile } else { Join-Path $repoRoot $LogFile }
$resolvedCommandBotLog = if ([System.IO.Path]::IsPathRooted($CommandBotLogFile)) { $CommandBotLogFile } else { Join-Path $repoRoot $CommandBotLogFile }
$launcher = Join-Path $repoRoot "scripts\run_signal_platform.ps1"
$commandBotLauncher = Join-Path $repoRoot "scripts\run_signal_platform_command_bot.ps1"

function Get-EnabledRouteStatus {
    param([string]$ConfigPath)

    if (-not (Test-Path $ConfigPath)) {
        return @()
    }

    try {
        $config = Get-Content -Path $ConfigPath -Raw | ConvertFrom-Json
    } catch {
        return @()
    }

    $statuses = @()
    foreach ($route in @($config.routes)) {
        if (-not $route.enabled) {
            continue
        }
        $snapshotPath = if ($route.health_snapshot_file) {
            if ([System.IO.Path]::IsPathRooted([string]$route.health_snapshot_file)) { [string]$route.health_snapshot_file } else { Join-Path $repoRoot ([string]$route.health_snapshot_file) }
        } else {
            Join-Path $repoRoot ("platform_output/{0}/health_snapshot.json" -f [string]$route.strategy_id)
        }

        $state = "NO SNAPSHOT"
        if (Test-Path $snapshotPath) {
            try {
                $snapshot = Get-Content -Path $snapshotPath -Raw | ConvertFrom-Json
                $quietReason = if ($snapshot.quiet_reason) { [string]$snapshot.quiet_reason } else { "active" }
                $state = "signals=$($snapshot.signals_found) fresh=$($snapshot.fresh_signals) quiet=$quietReason"
            } catch {
                $state = "SNAPSHOT READ FAILED"
            }
        }

        $statuses += [PSCustomObject]@{
            StrategyId = [string]$route.strategy_id
            State = $state
        }
    }

    return $statuses
}

function ConvertTo-LauncherPath {
    param([string]$Value)

    if (-not [System.IO.Path]::IsPathRooted($Value)) {
        return $Value
    }

    $normalizedRepo = [System.IO.Path]::GetFullPath($repoRoot).TrimEnd('\')
    $normalizedValue = [System.IO.Path]::GetFullPath($Value)
    if ($normalizedValue.StartsWith("$normalizedRepo\", [System.StringComparison]::OrdinalIgnoreCase)) {
        return $normalizedValue.Substring($normalizedRepo.Length + 1)
    }

    return $Value
}

function Get-BotRunnerProcesses {
    $procs = Get-CimInstance Win32_Process -Filter "Name='powershell.exe' OR Name='python.exe'" -ErrorAction SilentlyContinue
    if (-not $procs) {
        return @()
    }

    return @(
        $procs | Where-Object {
            $cmd = $_.CommandLine
            if (-not $cmd) { return $false }
            $cmd -like "*run_signal_platform.ps1*" -or
            ($cmd -like "*-m signal_platform*" -and $cmd -like "*serve*")
        }
    )
}

function Get-CommandBotProcesses {
    $procs = Get-CimInstance Win32_Process -Filter "Name='powershell.exe' OR Name='python.exe'" -ErrorAction SilentlyContinue
    if (-not $procs) {
        return @()
    }

    return @(
        $procs | Where-Object {
            $cmd = $_.CommandLine
            if (-not $cmd) { return $false }
            $cmd -like "*run_signal_platform_command_bot.ps1*" -or
            ($cmd -like "*-m signal_platform*" -and $cmd -like "*command-bot*")
        }
    )
}

function Get-EnvValue {
    param(
        [string]$Path,
        [string]$Key
    )

    if (-not (Test-Path $Path)) {
        return $null
    }

    foreach ($rawLine in Get-Content $Path) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            continue
        }
        $parts = $line.Split("=", 2)
        if ($parts[0].Trim() -ieq $Key) {
            return $parts[1].Trim().Trim('"').Trim("'")
        }
    }
    return $null
}

function Write-Line {
    param([string]$Text)
    if (-not $Quiet) {
        Write-Host $Text
    }
}

$runnerProcs = Get-BotRunnerProcesses
$isRunning = $runnerProcs.Count -gt 0
$commandBotToken = Get-EnvValue -Path $resolvedEnv -Key "DISCORD_BOT_TOKEN"
$shouldRunCommandBot = -not [string]::IsNullOrWhiteSpace($commandBotToken)
$commandBotProcs = Get-CommandBotProcesses
$isCommandBotRunning = $commandBotProcs.Count -gt 0

Write-Line "Repo: $repoRoot"
Write-Line "Config: $resolvedConfig"
Write-Line "Env: $resolvedEnv"
Write-Line "Log: $resolvedLog"
Write-Line "Command bot log: $resolvedCommandBotLog"
Write-Line "Runner status: $(if ($isRunning) { 'RUNNING' } else { 'STOPPED' })"
Write-Line "Command bot status: $(if ($shouldRunCommandBot) { if ($isCommandBotRunning) { 'RUNNING' } else { 'STOPPED' } } else { 'SKIPPED (no DISCORD_BOT_TOKEN)' })"

if ($runnerProcs.Count -gt 0 -and -not $Quiet) {
    $runnerProcs |
        Select-Object ProcessId, Name, CreationDate, CommandLine |
        Format-Table -AutoSize
}

if ($commandBotProcs.Count -gt 0 -and -not $Quiet) {
    $commandBotProcs |
        Select-Object ProcessId, Name, CreationDate, CommandLine |
        Format-Table -AutoSize
}

$routeStatuses = Get-EnabledRouteStatus -ConfigPath $resolvedConfig
if ($routeStatuses.Count -gt 0 -and -not $Quiet) {
    Write-Line "Enabled route status:"
    $routeStatuses | Format-Table -AutoSize | Out-String | Write-Host
}

if ($StatusOnly) {
    exit 0
}

if (-not $isRunning) {
    $logDir = Split-Path -Parent $resolvedLog
    if ($logDir) {
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    }

    $launcherConfig = ConvertTo-LauncherPath -Value $resolvedConfig
    $launcherEnv = ConvertTo-LauncherPath -Value $resolvedEnv
    $launcherLog = ConvertTo-LauncherPath -Value $resolvedLog

    Write-Line "No active bot runner found. Starting it now..."
    $started = Start-Process -FilePath "powershell.exe" `
        -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $launcher,
            "-Config", $launcherConfig,
            "-EnvFile", $launcherEnv,
            "-PollSeconds", "$PollSeconds",
            "-LogFile", $launcherLog
        ) `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden `
        -PassThru

    $isRunning = $false
    for ($attempt = 0; $attempt -lt 10; $attempt++) {
        Start-Sleep -Seconds 2
        $runnerProcs = Get-BotRunnerProcesses
        if ($runnerProcs.Count -gt 0) {
            $isRunning = $true
            break
        }
        if ($started -and -not (Get-Process -Id $started.Id -ErrorAction SilentlyContinue)) {
            break
        }
    }
}

if ($shouldRunCommandBot -and -not $isCommandBotRunning) {
    $commandBotLogDir = Split-Path -Parent $resolvedCommandBotLog
    if ($commandBotLogDir) {
        New-Item -ItemType Directory -Path $commandBotLogDir -Force | Out-Null
    }

    $launcherConfig = ConvertTo-LauncherPath -Value $resolvedConfig
    $launcherEnv = ConvertTo-LauncherPath -Value $resolvedEnv
    $launcherCommandBotLog = ConvertTo-LauncherPath -Value $resolvedCommandBotLog

    Write-Line "No active Discord command bot found. Starting it now..."
    $startedCommandBot = Start-Process -FilePath "powershell.exe" `
        -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $commandBotLauncher,
            "-Config", $launcherConfig,
            "-EnvFile", $launcherEnv,
            "-LogFile", $launcherCommandBotLog
        ) `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden `
        -PassThru

    $isCommandBotRunning = $false
    for ($attempt = 0; $attempt -lt 10; $attempt++) {
        Start-Sleep -Seconds 2
        $commandBotProcs = Get-CommandBotProcesses
        if ($commandBotProcs.Count -gt 0) {
            $isCommandBotRunning = $true
            break
        }
        if ($startedCommandBot -and -not (Get-Process -Id $startedCommandBot.Id -ErrorAction SilentlyContinue)) {
            break
        }
    }
}

if ($isRunning -and ($isCommandBotRunning -or -not $shouldRunCommandBot)) {
    Write-Line "Bots are running."
    exit 0
}

if (-not $isRunning) {
    Write-Error "Signal platform runner did not start correctly. Check $resolvedLog"
} else {
    Write-Error "Discord command bot did not start correctly. Check $resolvedCommandBotLog"
}
