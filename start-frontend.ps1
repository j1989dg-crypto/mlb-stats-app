# MLB AI Stats — Start Frontend
# Run this from any PowerShell window

$env:PATH = "D:\nodejs\node-v22.16.0-win-x64;$env:PATH"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MLB AI Stats - Frontend" -ForegroundColor Cyan
Write-Host "  http://localhost:3000" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Set-Location "D:\mlb-stats-app\frontend"
node "D:\nodejs\node-v22.16.0-win-x64\node_modules\npm\bin\npm-cli.js" run dev
