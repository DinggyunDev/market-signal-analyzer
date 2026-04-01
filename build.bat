@echo off
:: Set encoding to UTF-8 for Korean support in some consoles
chcp 65001 >nul

echo ============================================================
echo      Market Signal Analyzer Build Script
echo ============================================================
echo.

echo [1/4] Checking requirements...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install requirements.
    pause
    exit /b 1
)

echo [2/4] Checking PyInstaller...
pip install pyinstaller
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install PyInstaller.
    pause
    exit /b 1
)

echo [3/4] Cleaning old build files...
if exist dist rd /s /q dist
if exist build rd /s /q build
echo Clean finished.

echo [4/4] Building EXE file (Please wait about 1-2 min)...
pyinstaller --noconfirm MarketAnalyzer.spec
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo    BUILD SUCCESS!
echo    Check 'dist' folder for MarketAnalyzer.exe
echo ============================================================
echo.
echo Press any key to exit.
pause >nul
exit /b 0
