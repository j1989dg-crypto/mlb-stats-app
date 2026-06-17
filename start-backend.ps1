# MLB AI Stats — Start Backend
# Run this from any PowerShell window

$env:PYTHONPATH      = "D:\mlb-stats-app\site-packages"
$env:TEMP            = "D:\tmp"
$env:TMP             = "D:\tmp"
$env:PYTHONIOENCODING = "utf-8"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MLB AI Stats - Backend API" -ForegroundColor Cyan
Write-Host "  http://localhost:8000" -ForegroundColor Green
Write-Host "  http://localhost:8000/docs  (API Explorer)" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Set-Location "D:\mlb-stats-app\backend"
& "D:\mlb-stats-app\venv\Scripts\python.exe" -W ignore main.py
