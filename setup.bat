@echo off
setlocal
cd /d "%~dp0"

if not exist "config.json" (
    if exist "config.example.json" (
        copy "config.example.json" "config.json" >nul
        echo Created config.json from config.example.json
    ) else (
        echo config.example.json not found. The GUI will create config.json for you.
    )
) else (
    echo config.json already exists. Skipped.
)

if not exist "logs" mkdir "logs"

echo.
echo Next steps:
echo   1. Double-click run.bat to open the GUI
echo   2. Enter your account settings and click "Save config"
echo   3. Click "Start"
echo.
pause
