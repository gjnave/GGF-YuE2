@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Get Going Fast - YuE2 Music Studio Setup
set "PYTHONIOENCODING=utf-8"
set "APP=%CD%\GGF-YuE2"
set "UV_EXE=%APP%\runtime\uv.exe"
set "CACHE=%CD%\installer-cache"
if exist "about.nfo" type "about.nfo"
if exist "disclaimer.md" type "disclaimer.md"
echo.
echo YuE2 Music Studio - Windows 64-bit, NVIDIA GPU, current driver.
echo Private Python 3.12 is installed automatically. Global Python is not used.
echo Allow 12 GB of disk space plus space for generated songs.
echo YuE2 model weights and the optional instrumental LoRA are CC BY-NC 4.0.
if not defined GGF_UNATTENDED pause
if not exist "%CACHE%" mkdir "%CACHE%"
if not defined GGF_SOURCE_PRIMARY set "GGF_SOURCE_PRIMARY=https://codeberg.org/Cognibuild/GGF-YuE2/archive/main.zip"
if not defined GGF_SOURCE_SECONDARY set "GGF_SOURCE_SECONDARY=https://github.com/gjnave/GGF-YuE2/archive/refs/heads/main.zip"
echo Downloading app source from Codeberg...
call :source "%GGF_SOURCE_PRIMARY%"
if not errorlevel 1 goto source_ready
echo Trying GitHub fallback...
call :source "%GGF_SOURCE_SECONDARY%"
if errorlevel 1 goto failed
:source_ready
if not exist "%APP%" mkdir "%APP%"
if exist "%APP%\app.py" call :backup
if errorlevel 1 goto failed
xcopy "%SOURCE_ROOT%\*" "%APP%\" /e /i /y >nul
if errorlevel 1 goto failed
if /i "%~1"=="/files-only" exit /b 0
if not exist "%APP%\runtime" mkdir "%APP%\runtime"
if exist "%UV_EXE%" goto uv_ready
curl.exe --fail --location --retry 3 --output "%CACHE%\uv-0.12.13.zip" "https://github.com/astral-sh/uv/releases/download/0.12.13/uv-x86_64-pc-windows-msvc.zip"
if errorlevel 1 goto failed
certutil -hashfile "%CACHE%\uv-0.12.13.zip" SHA256 | findstr /i /c:"a86c9dc7bad9b03f388583b7187c05fe9951c2e0d392217e8fd43d97787f6ec2" >nul
if errorlevel 1 goto failed
tar.exe -xf "%CACHE%\uv-0.12.13.zip" -C "%APP%\runtime" uv.exe
if errorlevel 1 goto failed
:uv_ready
set "UV_PYTHON_INSTALL_DIR=%APP%\runtime\python"
set "UV_PYTHON_DOWNLOADS=automatic"
set "VIRTUAL_ENV="
if exist "%APP%\.venv-3.12\Scripts\python.exe" goto venv_ready
"%UV_EXE%" venv --managed-python --python 3.12 "%APP%\.venv-3.12"
if errorlevel 1 goto failed
:venv_ready
set "PY=%APP%\.venv-3.12\Scripts\python.exe"
"%PY%" -c "import sys; assert sys.version_info[:2]==(3,12) and sys.maxsize>2**32, 'Requires private 64-bit Python 3.12'"
if errorlevel 1 goto failed
"%UV_EXE%" pip install --python "%PY%" -r "%APP%\requirements.txt"
if errorlevel 1 goto failed
"%UV_EXE%" pip check --python "%PY%"
if errorlevel 1 goto failed
if /i "%~1"=="/dependencies-only" exit /b 0
"%PY%" "%APP%\update_app.py"
if errorlevel 1 goto failed
"%PY%" "%APP%\setup_runtime.py"
if errorlevel 1 goto failed
set "QUANT=%~1"
if /i "%QUANT%"=="q4" goto models
if /i "%QUANT%"=="q8" goto models
if /i "%QUANT%"=="both" goto models
set "QUANT=q8"
if defined GGF_UNATTENDED goto models
echo 1. Q8 higher fidelity - recommended  2. Q4 lower memory  3. Both
choice /c 123 /n /t 10 /d 1 /m "Choose 1-3 [Q8 in 10 seconds]: "
if errorlevel 3 set "QUANT=both"
if errorlevel 2 if not errorlevel 3 set "QUANT=q4"
:models
if /i "%QUANT%"=="q4" goto q4
"%PY%" "%APP%\yue2_gguf_gui.py" --download q8
if errorlevel 1 goto failed
if /i "%QUANT%"=="q8" goto verify
:q4
"%PY%" "%APP%\yue2_gguf_gui.py" --download q4
if errorlevel 1 goto failed
:verify
"%PY%" "%APP%\yue2_gguf_gui.py" --check
if errorlevel 1 goto failed
echo Setup complete. Double-click RUN.bat. Optional instrumental LoRA is in Settings.
if not defined GGF_UNATTENDED pause
exit /b 0
:failed
echo Setup stopped. Existing files, models, outputs and partial downloads are preserved.
if not defined GGF_UNATTENDED pause
exit /b 1
:source
set "SOURCE_ROOT="
set "STAGE=%CACHE%\source-%RANDOM%-%RANDOM%"
mkdir "%STAGE%"
if errorlevel 1 exit /b 1
curl.exe --fail --location --retry 2 --connect-timeout 20 --output "%STAGE%\source.zip" "%~1"
if errorlevel 1 exit /b 1
tar.exe -xf "%STAGE%\source.zip" -C "%STAGE%"
if errorlevel 1 exit /b 1
for /d %%D in ("%STAGE%\*") do if exist "%%D\app.py" if exist "%%D\yue2_gguf_gui.py" if exist "%%D\requirements.txt" if exist "%%D\setup_runtime.py" if exist "%%D\update_app.py" if exist "%%D\model_manifest.json" if exist "%%D\release_sources.json" if exist "%%D\ui.css" set "SOURCE_ROOT=%%D"
if not defined SOURCE_ROOT exit /b 1
exit /b 0
:backup
set "BACKUP=%CACHE%\before-source-%RANDOM%-%RANDOM%"
mkdir "%BACKUP%"
if errorlevel 1 exit /b 1
xcopy "%APP%\*.*" "%BACKUP%\" /i /y >nul
if errorlevel 2 exit /b 1
for %%D in (assets tests) do if exist "%APP%\%%D" (
  xcopy "%APP%\%%D\*" "%BACKUP%\%%D\" /e /i /y >nul
  if errorlevel 2 exit /b 1
)
exit /b 0
