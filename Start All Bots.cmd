@echo off
setlocal
cd /d "C:\Users\Seeker\Documents\swing-pr1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Seeker\Documents\swing-pr1\scripts\ensure_signal_platform.ps1"
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Seeker\Documents\swing-pr1\scripts\ensure_parabolic_paper.ps1" -Profile "NAS100_PARABOLIC_PAPER" -EnvFile "parabolic-exhaustion-bot\.env"
echo.
pause
