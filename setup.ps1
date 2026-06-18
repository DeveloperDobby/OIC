$ErrorActionPreference = "Stop"

Write-Host "Preparing config.json..." -ForegroundColor Cyan

if (!(Test-Path "config.json")) {
    if (Test-Path "config.example.json") {
        Copy-Item "config.example.json" "config.json"
        Write-Host "Created config.json from config.example.json"
    } else {
        Write-Host "config.example.json not found." -ForegroundColor Yellow
    }
} else {
    Write-Host "config.json already exists. Skipped."
}

if (!(Test-Path "logs")) { New-Item -ItemType Directory -Path "logs" | Out-Null }

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Edit config.json (or run the GUI: .\run.bat)"
Write-Host "2. Start with the GUI, or via Docker: .\start.ps1"
