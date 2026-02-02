@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo [1/2] Closing running CamouFlow (if any)...
taskkill /F /IM CamouFlow.exe >nul 2>&1

echo [2/2] Building with PyInstaller...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

py -m PyInstaller camouflow.spec --noconfirm --clean || exit /b 1

echo.
echo Build done: dist\CamouFlow\CamouFlow.exe
endlocal
