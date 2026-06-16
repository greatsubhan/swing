@echo off
rem ============================================================
rem  RUN_signal_platform.bat
rem  Starts the Signal Platform in SERVE mode.
rem  Uses: scripts\run_signal_platform.ps1
rem
rem  Parameters (edit below as needed):
rem    -Config        Path to platform config JSON
rem                   Default: config\platform.example.json
rem    -EnvFile        Path to .env file (API keys etc.)
rem                   Default: .env
rem    -PollSeconds    How often to poll (seconds). Default: 30
rem    -MaxCycles      Limit run cycles (blank = run forever)
rem    -NoRunImmediately  Wait one full poll before first run
rem    -DryRun         Run without dispatching real signals
rem
rem  Logs saved to: logs\signal_platform.log
rem ============================================================
cd /d C:\Users\Seeker\Documents\swing-pr1
title Signal Platform - LIVE SERVE
powershell.exe -ExecutionPolicy Bypass -File scripts\run_signal_platform.ps1 ^-Config "config\platform.example.json" ^-EnvFile ".env" ^-PollSeconds 30
pause
