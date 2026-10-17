@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Get Going Fast - YuE2 Music Studio
if exist "about.nfo" type "about.nfo"
if not exist ".venv-3.12\Scripts\python.exe" goto missing
set "PYTHONIOENCODING=utf-8"
".venv-3.12\Scripts\python.exe" "app.py"
if errorlevel 1 pause
exit /b %errorlevel%
:missing
echo Complete the manual setup steps in README.md, or use the separate Get Going Fast member installer.
pause
exit /b 1
