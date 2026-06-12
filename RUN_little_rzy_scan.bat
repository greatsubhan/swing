@echo off
cd /d C:\Users\Seeker\Documents\swing-pr1
title Little RZY Scan
echo Running one Little RZY Discord route scan...
powershell.exe -ExecutionPolicy Bypass -File scripts\run_signal_platform_scan.ps1 ^-Strategy "little_rzy" ^-Config "config\platform.example.json" ^-EnvFile ".env" ^-LogFile "logs\little_rzy_scan.log"
pause
