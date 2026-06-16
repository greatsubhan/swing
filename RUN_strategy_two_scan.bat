@echo off
cd /d C:\Users\Seeker\Documents\swing-pr1
title Strategy Two Scan
echo Running one Strategy Two Discord route scan...
powershell.exe -ExecutionPolicy Bypass -File scripts\run_signal_platform_scan.ps1 ^-Strategy "strategy_two" ^-Config "config\platform.example.json" ^-EnvFile ".env" ^-LogFile "logs\strategy_two_scan.log"
pause
