@echo off
cd /d C:\Users\Seeker\Documents\swing-pr1
title Strategy Five Scan
echo Running one Strategy Five Discord route scan...
powershell.exe -ExecutionPolicy Bypass -File scripts\run_signal_platform_scan.ps1 ^-Strategy "strategy_five" ^-Config "config\platform.example.json" ^-EnvFile ".env" ^-LogFile "logs\strategy_five_scan.log"
pause
