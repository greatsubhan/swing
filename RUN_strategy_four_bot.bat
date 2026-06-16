@echo off
rem ============================================================
rem  RUN_strategy_four_bot.bat
rem  Strategy Four Bot - CWT (M5, core-mixed watchlist)
rem
rem  NOTE: strategy_four runs as a ROUTE inside signal_platform.
rem  To run ALL bots together, use RUN_signal_platform.bat.
rem
rem  Strategy Config (from platform.example.json):
rem    strategy_id   : strategy_four
rem    watchlist     : core-mixed
rem    granularity   : M5   higher_timeframe: H1
rem    interval      : every 5 min
rem    dispatch      : discord
rem    output_dir    : platform_output/strategy_four
rem    weekly+monthly reports: enabled
rem
rem  Logs saved to: logs\signal_platform.log
rem ============================================================
cd /d C:\Users\Seeker\Documents\swing-pr1
title Strategy Four Bot - via Signal Platform
echo Starting signal_platform with strategy_four config...
powershell.exe -ExecutionPolicy Bypass -File scripts\run_signal_platform.ps1 ^-Config "config\platform.example.json" ^-EnvFile ".env" ^-PollSeconds 30
pause
