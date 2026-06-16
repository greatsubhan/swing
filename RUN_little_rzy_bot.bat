@echo off
rem ============================================================
rem  RUN_little_rzy_bot.bat
rem  Runs the Little RZY Bot in LIVE SCAN mode.
rem
rem  Parameters (edit below as needed):
rem    --scan          Enable live OANDA watchlist scanning
rem    --watchlist     Watchlist name (default: primary-4h)
rem    --granularity   OANDA timeframe: M15, H1, H4, D (default: H4)
rem    --oanda-env     practice or live (default: practice)
rem    --oanda-price   M, B, or A (default: M = mid)
rem    --provider      yahoo or oanda (default: oanda)
rem
rem  API keys loaded from: .env
rem  Outputs saved to: backtest_output\
rem ============================================================
cd /d C:\Users\Seeker\Documents\swing-pr1
rem Load .env into environment
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if not "%%A"=="" if not "%%A:~0,1%%"=="#" set "%%A=%%B"
)
title Little RZY Bot - Live Scan
echo Starting Little RZY Bot (live scan, H4, practice)...
python -m little_rzy_bot --scan --watchlist primary-4h --granularity H4 --oanda-env practice --oanda-price M
pause
