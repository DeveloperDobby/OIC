$ErrorActionPreference = "Stop"

if (!(Test-Path "config.json")) {
    Write-Host "config.json not found. Running setup.ps1 first..." -ForegroundColor Yellow
    .\setup.ps1
    Write-Host ""
    Write-Host "Please edit config.json before starting." -ForegroundColor Red
    exit 1
}

docker compose up -d --build

Write-Host ""
Write-Host "Started. To view logs, run:" -ForegroundColor Green
Write-Host ".\logs.ps1"
