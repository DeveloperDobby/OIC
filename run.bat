@echo off
setlocal
cd /d "%~dp0"

echo Starting OCI ARM Auto Launcher GUI...

if exist "oci-arm-auto-gui.exe" (
    start "" "oci-arm-auto-gui.exe"
    echo GUI launched. You can close this window.
    timeout /t 3 >nul
) else (
    echo oci-arm-auto-gui.exe not found. Trying Python source...
    python gui.py
    if errorlevel 1 (
        echo.
        echo Failed to start. Make sure Python is installed, or use the exe.
        pause
    )
)
