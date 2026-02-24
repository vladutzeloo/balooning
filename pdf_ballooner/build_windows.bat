@echo off
setlocal EnableDelayedExpansion

echo ================================================
echo   PDF Ballooner ^| Windows Build Script
echo ================================================
echo.

:: -------------------------------------------------------
:: 1. Verify Python is available
:: -------------------------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo         Install Python 3.10+ from https://python.org
    echo         and make sure to tick "Add Python to PATH".
    pause & exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo Python: %%v
echo.

:: -------------------------------------------------------
:: 2. Install / upgrade runtime + build dependencies
:: -------------------------------------------------------
echo [1/4] Installing dependencies...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
python -m pip install pyinstaller --quiet
if errorlevel 1 (
    echo [ERROR] pip install failed. Check your internet connection.
    pause & exit /b 1
)
echo       Done.
echo.

:: -------------------------------------------------------
:: 3. Clean previous build artefacts
:: -------------------------------------------------------
echo [2/4] Cleaning previous build...
if exist build  rmdir /s /q build
if exist "dist\PDF Ballooner" rmdir /s /q "dist\PDF Ballooner"
echo       Done.
echo.

:: -------------------------------------------------------
:: 4. Run PyInstaller
:: -------------------------------------------------------
echo [3/4] Building executable (this takes 1-3 minutes)...
pyinstaller PDF_Ballooner.spec --noconfirm
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller failed. See output above.
    pause & exit /b 1
)
echo.

:: -------------------------------------------------------
:: 5. Report
:: -------------------------------------------------------
echo [4/4] Build complete!
echo.
echo ================================================
echo   Output:  dist\PDF Ballooner\PDF Ballooner.exe
echo.
echo   To distribute: zip the entire
echo   "dist\PDF Ballooner\" folder and send it.
echo   The recipient just unzips and double-clicks
echo   "PDF Ballooner.exe" — no Python needed.
echo ================================================
echo.

:: Optional: open the output folder in Explorer
start "" "dist\PDF Ballooner"

pause
