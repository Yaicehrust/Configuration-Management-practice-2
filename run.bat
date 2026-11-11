@echo off
setlocal
cd /d "%~dp0"
py -3 -m src.main %*
exit /b %ERRORLEVEL%
