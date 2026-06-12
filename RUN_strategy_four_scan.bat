@echo off
cd /d C:\Users\Seeker\Documents\swing-pr1
title Strategy Four Scan
echo Running one Strategy Four Discord route scan...
powershell.exe -ExecutionPolicy Bypass -File scripts\run_signal_platform_scan.ps1 ^-Strategy "strategy_four" ^-Config "config\platform.example.json" ^-EnvFile ".env" ^-LogFile "logs\strategy_four_scan.log"
pause
