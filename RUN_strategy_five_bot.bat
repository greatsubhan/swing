@echo off
rem ============================================================
rem  RUN_strategy_five_bot.bat
rem  Strategy Five Bot - SIP Classic (Daily, full-classic watchlist)
rem
rem  NOTE: strategy_five runs as a ROUTE inside signal_platform.
rem  To run ALL bots together, use RUN_signal_platform.bat.
rem
rem  Strategy Config (from platform.example.json):
rem    strategy_id   : strategy_five
rem    watchlist     : full-classic
rem    granularity   : D (Daily)   higher_timeframe: 1mo
rem    interval      : every 1440 min (once per day)
rem    dispatch      : discord
rem    output_dir    : platform_output/strategy_five
rem
rem  Logs saved to: logs\signal_platform.log
rem ============================================================
cd /d C:\Users\Seeker\Documents\swing-pr1
title Strategy Five Bot - via Signal Platform
echo Starting signal_platform with strategy_five config...
powershell.exe -ExecutionPolicy Bypass -File scripts\run_signal_platform.ps1 ^-Config "config\platform.example.json" ^-EnvFile ".env" ^-PollSeconds 30
pause
