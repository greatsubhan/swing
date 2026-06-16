param(
    [string]$Config = "config/platform.example.json",
    [string]$EnvFile = ".env",
    [string]$PythonExe = "",
    [string]$LogFile = "logs/signal_platform_command_bot.log",
    [string]$BotToken = ""
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

function Write-CommandBotLog {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $resolvedLog -Value "[$timestamp] $Message" -Encoding utf8
}

$arguments = @(
    "-u",
    "-m", "signal_platform",
    "--env-file", $EnvFile,
    "command-bot",
    "--config", $Config
)

if (-not [string]::IsNullOrWhiteSpace($BotToken)) {
    $arguments += @("--bot-token", $BotToken)
}

$attempt = 0
while ($true) {
    $attempt += 1
    Write-CommandBotLog "Heartbeat: command bot wrapper alive | attempt=$attempt"
    Write-CommandBotLog "Starting: $PythonExe $($arguments -join ' ')"
    & $PythonExe @arguments *>> $resolvedLog
    $exitCode = $LASTEXITCODE
    Write-CommandBotLog "ExitCode: $exitCode"
    if ($exitCode -eq 0) {
        Write-CommandBotLog "Command bot exited cleanly; restarting in 5 seconds."
        Start-Sleep -Seconds 5
        continue
    }
    Write-CommandBotLog "Command bot crashed; restarting in 10 seconds."
    Start-Sleep -Seconds 10
}
