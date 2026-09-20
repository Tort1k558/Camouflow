@echo off
setlocal
cd /d "%~dp0"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss-fff"') do set "BUILD_ID=%%i"
if not defined BUILD_ID exit /b 1
if not exist ".venv\Scripts\python.exe" (
    echo Missing .venv\Scripts\python.exe
    exit /b 1
)
".venv\Scripts\python.exe" -m PyInstaller camouflow.spec --distpath "dist\%BUILD_ID%" --workpath "build\%BUILD_ID%" || exit /b 1
echo Build done: dist\%BUILD_ID%\CamouFlow\CamouFlow.exe
endlocal
