@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
set "BUILD_ID="
for /f %%i in ('powershell -NoProfile -Command "$env:PSModulePath=[Environment]::GetEnvironmentVariable('PSModulePath','Machine'); Get-Date -Format yyyyMMdd-HHmmss-fff"') do set "BUILD_ID=%%i"
if not defined BUILD_ID exit /b 1
if not exist ".venv\Scripts\python.exe" (
    echo Missing .venv\Scripts\python.exe
    exit /b 1
)
if defined CAMOUFLOW_BUILD_ROOT (
    for %%i in ("%CAMOUFLOW_BUILD_ROOT%") do set "BUILD_ROOT=%%~fi"
) else (
    set "BUILD_ROOT=%CD%"
)
set "TEMP=%BUILD_ROOT%\build\%BUILD_ID%-tmp"
set "TMP=%TEMP%"
mkdir "%TEMP%" || exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --clean camouflow.spec --distpath "%BUILD_ROOT%\dist\%BUILD_ID%" --workpath "%BUILD_ROOT%\build\%BUILD_ID%" || exit /b 1
echo Build done: "%BUILD_ROOT%\dist\%BUILD_ID%\CamouFlow\CamouFlow.exe"
endlocal
