# Builds the portable executables with PyInstaller.
# Run on Windows in this folder:  .\build.ps1
#
# The GUI is built as --onedir (a folder) so it starts INSTANTLY.
# (--onefile must unpack the whole oci SDK to a temp dir on every launch,
#  which makes the first start take a long time.)
#
# Produces:
#   dist\oci-arm-auto-gui\oci-arm-auto-gui.exe   (GUI, fast start)
#   dist\oci-arm-auto.exe                        (headless CLI, single file)
$ErrorActionPreference = "Stop"

Write-Host "Installing build dependencies..." -ForegroundColor Cyan
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

Write-Host "Building GUI executable (onedir, fast start)..." -ForegroundColor Cyan
pyinstaller --noconfirm --onedir --windowed --name oci-arm-auto-gui `
    --collect-all oci `
    --collect-all certifi `
    gui.py

Write-Host "Building CLI executable (onefile)..." -ForegroundColor Cyan
pyinstaller --noconfirm --onefile --name oci-arm-auto `
    --collect-all oci `
    --collect-all certifi `
    create_instance.py

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "  GUI: dist\oci-arm-auto-gui\oci-arm-auto-gui.exe"
Write-Host "  CLI: dist\oci-arm-auto.exe"
Write-Host "Keep the GUI exe together with its _internal folder."
