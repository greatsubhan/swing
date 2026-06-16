@echo off
rem ============================================================
rem  RUN_strategy_two_bot.bat
rem  Strategy Two Bot - Trend Current (H4, core-4h watchlist)
rem
rem  NOTE: strategy_two runs as a ROUTE inside signal_platform.
rem  This bat starts signal_platform with ONLY strategy_two enabled
rem  by using the platform config. To run ALL bots together,
rem  use RUN_signal_platform.bat instead.
rem
rem  Strategy Config (from platform.example.json):
rem    strategy_id   : strategy_two
rem    watchlist     : core-4h
rem    granularity   : H4   higher_timeframe: 1d
rem    interval      : every 240 min
rem    dispatch      : discord
rem    output_dir    : platform_output/strategy_two
rem
rem  Logs saved to: logs\signal_platform.log
rem ============================================================
cd /d C:\Users\Seeker\Documents\swing-pr1
title Strategy Two Bot - via Signal Platform
echo Starting signal_platform with strategy_two config...
powershell.exe -ExecutionPolicy Bypass -File scripts\run_signal_platform.ps1 ^-Config "config\platform.example.json" ^-EnvFile ".env" ^-PollSeconds 30
pause
