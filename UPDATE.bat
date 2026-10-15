@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if not exist "GGF-YuE2\.venv-3.12\Scripts\python.exe" goto missing
"GGF-YuE2\.venv-3.12\Scripts\python.exe" "GGF-YuE2\update_app.py"
if errorlevel 1 goto failed
echo Updated. Double-click RUN.bat.
if not defined GGF_UNATTENDED pause
exit /b 0
:missing
echo Run INSTALL.bat first.
:failed
echo Update stopped. Check the message above.
if not defined GGF_UNATTENDED pause
exit /b 1
