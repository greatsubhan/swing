param(
    [string]$Config = "config/platform.example.json",
    [int]$PollSeconds = 30,
    [string]$EnvFile = ".env",
    [Nullable[int]]$MaxCycles = $null,
    [switch]$NoRunImmediately,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if ($DryRun) {
    Write-Host "Running signal platform in dry-run mode"
    $tempConfig = Join-Path $repoRoot "platform.example.dryrun.json"
    $content = Get-Content $Config -Raw
    $content = $content -replace '"dispatch": "discord"', '"dispatch": "none"'
    Set-Content -Path $tempConfig -Value $content
    if ($null -ne $MaxCycles) {
        if ($NoRunImmediately) {
            python -m signal_platform --env-file $EnvFile serve --config $tempConfig --poll-seconds $PollSeconds --max-cycles $MaxCycles --no-run-immediately
        } else {
            python -m signal_platform --env-file $EnvFile serve --config $tempConfig --poll-seconds $PollSeconds --max-cycles $MaxCycles
        }
    } else {
        if ($NoRunImmediately) {
            python -m signal_platform --env-file $EnvFile serve --config $tempConfig --poll-seconds $PollSeconds --no-run-immediately
        } else {
            python -m signal_platform --env-file $EnvFile serve --config $tempConfig --poll-seconds $PollSeconds
        }
    }
    Remove-Item $tempConfig -ErrorAction SilentlyContinue
} else {
    if ($null -ne $MaxCycles) {
        if ($NoRunImmediately) {
            python -m signal_platform --env-file $EnvFile serve --config $Config --poll-seconds $PollSeconds --max-cycles $MaxCycles --no-run-immediately
        } else {
            python -m signal_platform --env-file $EnvFile serve --config $Config --poll-seconds $PollSeconds --max-cycles $MaxCycles
        }
    } else {
        if ($NoRunImmediately) {
            python -m signal_platform --env-file $EnvFile serve --config $Config --poll-seconds $PollSeconds --no-run-immediately
        } else {
            python -m signal_platform --env-file $EnvFile serve --config $Config --poll-seconds $PollSeconds
        }
    }
}
