@echo off
rem ============================================================
rem  RUN_nas100_parabolic_paper.bat
rem  Starts the NAS100 parabolic paper-forward runner.
rem  Uses: scripts\run_parabolic_paper.ps1
rem
rem  Profile         : NAS100_PARABOLIC_PAPER
rem  Provider        : oanda
rem  Env file        : parabolic-exhaustion-bot\.env
rem  Log file        : logs\parabolic_paper.log
rem ============================================================
cd /d C:\Users\Seeker\Documents\swing-pr1
title NAS100 Parabolic Paper
echo Starting NAS100 parabolic paper-forward runner...
powershell.exe -ExecutionPolicy Bypass -File scripts\run_parabolic_paper.ps1 ^-Profile "NAS100_PARABOLIC_PAPER" ^-EnvFile "parabolic-exhaustion-bot\.env"
pause
