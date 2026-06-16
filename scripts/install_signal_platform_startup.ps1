param(
    [string]$TaskName = "Signal Platform - Little RZY",
    [string]$Config = "config/platform.example.json",
    [string]$EnvFile = ".env",
    [int]$PollSeconds = 30,
    [string]$LogFile = "logs/signal_platform.log"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$ensureScript = Join-Path $repoRoot "scripts\ensure_signal_platform.ps1"
$resolvedConfig = Join-Path $repoRoot $Config
$resolvedEnv = Join-Path $repoRoot $EnvFile
$resolvedLog = Join-Path $repoRoot $LogFile
$startupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$startupCmd = Join-Path $startupDir "Start All Bots.cmd"

$actionArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$ensureScript`"",
    "-Config", "`"$resolvedConfig`"",
    "-EnvFile", "`"$resolvedEnv`"",
    "-PollSeconds", "$PollSeconds",
    "-LogFile", "`"$resolvedLog`"",
    "-Quiet"
) -join " "

New-Item -ItemType Directory -Path $startupDir -Force | Out-Null
@(
    '@echo off',
    'cd /d "C:\Users\Seeker\Documents\swing-pr1"',
    'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Seeker\Documents\swing-pr1\scripts\ensure_signal_platform.ps1" -Quiet'
) | Set-Content -Path $startupCmd -Encoding ASCII

try {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $actionArgs
    $startupTrigger = New-ScheduledTaskTrigger -AtStartup
    $logonTrigger = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger @($startupTrigger, $logonTrigger) `
        -Settings $settings `
        -Principal $principal `
        -Force | Out-Null

    Write-Host "Installed startup task: $TaskName"
} catch {
    Write-Warning "Scheduled task install failed. Startup-folder launcher was created instead."
}

Write-Host "Startup launcher installed: $startupCmd"
