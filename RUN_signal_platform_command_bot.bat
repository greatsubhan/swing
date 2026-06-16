@echo off
cd /d C:\Users\Seeker\Documents\swing-pr1
title Signal Platform - Discord Command Bot
powershell.exe -ExecutionPolicy Bypass -File scripts\run_signal_platform_command_bot.ps1 ^-Config "config\platform.example.json" ^-EnvFile ".env"
pause
