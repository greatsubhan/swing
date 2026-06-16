param(
    [string]$Profile = "NAS100_PARABOLIC_PAPER",
    [string]$EnvFile = "parabolic-exhaustion-bot\.env",
    [string]$PythonExe = "",
    [string]$LogFile = "logs\parabolic_paper.log",
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

$resolvedEnv = if ([System.IO.Path]::IsPathRooted($EnvFile)) { $EnvFile } else { Join-Path $repoRoot $EnvFile }
$resolvedLog = if ([System.IO.Path]::IsPathRooted($LogFile)) { $LogFile } else { Join-Path $repoRoot $LogFile }
$launcher = Join-Path $repoRoot "scripts\run_parabolic_paper.ps1"

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

function Get-ParabolicRunnerProcesses {
    $procs = Get-CimInstance Win32_Process -Filter "Name='powershell.exe' OR Name='python.exe'" -ErrorAction SilentlyContinue
    if (-not $procs) {
        return @()
    }

    return @(
        $procs | Where-Object {
            $cmd = $_.CommandLine
            if (-not $cmd) { return $false }
            $cmd -like "*run_parabolic_paper.ps1*" -or
            ($cmd -like "*-m parabolic_exhaustion.live.run*" -and $cmd -like "*$Profile*")
        }
    )
}

function Write-Line {
    param([string]$Text)
    if (-not $Quiet) {
        Write-Host $Text
    }
}

$runnerProcs = Get-ParabolicRunnerProcesses
$isRunning = $runnerProcs.Count -gt 0

Write-Line "Repo: $repoRoot"
Write-Line "Profile: $Profile"
Write-Line "Env: $resolvedEnv"
Write-Line "Log: $resolvedLog"
Write-Line "Runner status: $(if ($isRunning) { 'RUNNING' } else { 'STOPPED' })"

if ($runnerProcs.Count -gt 0 -and -not $Quiet) {
    $runnerProcs |
        Select-Object ProcessId, Name, CreationDate, CommandLine |
        Format-Table -AutoSize
}

if ($StatusOnly) {
    exit 0
}

if (-not $isRunning) {
    $logDir = Split-Path -Parent $resolvedLog
    if ($logDir) {
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    }

    $launcherEnv = ConvertTo-LauncherPath -Value $resolvedEnv
    $launcherLog = ConvertTo-LauncherPath -Value $resolvedLog

    Write-Line "No active parabolic paper runner found. Starting it now..."
    $started = Start-Process -FilePath "powershell.exe" `
        -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $launcher,
            "-Profile", $Profile,
            "-EnvFile", $launcherEnv,
            "-LogFile", $launcherLog
        ) `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden `
        -PassThru

    $isRunning = $false
    for ($attempt = 0; $attempt -lt 10; $attempt++) {
        Start-Sleep -Seconds 2
        $runnerProcs = Get-ParabolicRunnerProcesses
        if ($runnerProcs.Count -gt 0) {
            $isRunning = $true
            break
        }
        if ($started -and -not (Get-Process -Id $started.Id -ErrorAction SilentlyContinue)) {
            break
        }
    }
}

if ($isRunning) {
    Write-Line "Parabolic paper runner is active."
    exit 0
}

Write-Error "Parabolic paper runner did not start correctly. Check $resolvedLog"
