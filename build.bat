@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo [1/3] Installing dependencies...
py -m pip install --upgrade pip || exit /b 1
py -m pip install -r requirements.txt || exit /b 1
py -m pip install pyinstaller || exit /b 1

echo [2/3] Closing running CamouFlow (if any)...
taskkill /F /IM CamouFlow.exe >nul 2>&1

echo [3/3] Building with PyInstaller...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

py -m PyInstaller camouflow.spec --noconfirm --clean || exit /b 1

echo.
echo Build done: dist\CamouFlow\CamouFlow.exe
endlocal
