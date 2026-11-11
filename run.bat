@echo off
setlocal
py -3 -m src.main %*
exit /b %ERRORLEVEL%
