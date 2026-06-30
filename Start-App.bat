@echo off
powershell.exe -ExecutionPolicy Bypass -File "%~dp0Start-App.ps1"
echo.
echo Exit code: %ERRORLEVEL%
pause
