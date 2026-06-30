@echo off
powershell.exe -ExecutionPolicy Bypass -File "%~dp0Update-App.ps1"
echo.
echo Exit code: %ERRORLEVEL%
pause
