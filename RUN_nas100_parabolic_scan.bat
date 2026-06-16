@echo off
cd /d C:\Users\Seeker\Documents\swing-pr1
title NAS100 Parabolic Scan
echo Running one NAS100 parabolic Discord scan...
powershell.exe -ExecutionPolicy Bypass -File scripts\run_parabolic_scan.ps1 ^-Profile "NAS100_PARABOLIC_PAPER" ^-EnvFile "parabolic-exhaustion-bot\.env" ^-LogFile "logs\parabolic_scan.log"
pause
