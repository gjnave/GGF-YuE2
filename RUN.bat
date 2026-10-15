@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Get Going Fast - YuE2 Music Studio
if exist "about.nfo" type "about.nfo"
if not exist "GGF-YuE2\.venv-3.12\Scripts\python.exe" goto missing
set "PYTHONIOENCODING=utf-8"
"GGF-YuE2\.venv-3.12\Scripts\python.exe" "GGF-YuE2\app.py"
if errorlevel 1 pause
exit /b %errorlevel%
:missing
echo Run INSTALL.bat first.
pause
exit /b 1
