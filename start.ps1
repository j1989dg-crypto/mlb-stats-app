# MLB AI Stats App — Startup Script (Windows PowerShell)
# Run this script to start both backend and frontend

$NODE = "D:\nodejs\node-v22.16.0-win-x64"
$SITE_PACKAGES = "D:\mlb-stats-app\site-packages"
$BACKEND = "D:\mlb-stats-app\backend"
$FRONTEND = "D:\mlb-stats-app\frontend"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ⚾  MLB AI Stats App" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- Start Backend ---
Write-Host "🐍 Starting Python backend on http://localhost:8000 ..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    param($bp, $sp)
    $env:PYTHONPATH = $sp
    $env:TMPDIR = "D:\tmp"
    $env:TEMP  = "D:\tmp"
    $env:TMP   = "D:\tmp"
    Set-Location $bp
    & "D:\mlb-stats-app\venv\Scripts\python.exe" main.py
} -ArgumentList $BACKEND, $SITE_PACKAGES

Start-Sleep -Seconds 3

# --- Start Frontend ---
Write-Host "⚡ Starting Next.js frontend on http://localhost:3000 ..." -ForegroundColor Yellow
$frontendJob = Start-Job -ScriptBlock {
    param($fp, $node)
    $env:PATH = "$node;$env:PATH"
    Set-Location $fp
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    & node "$node\node_modules\npm\bin\npm-cli.js" run dev
} -ArgumentList $FRONTEND, $NODE

Write-Host ""
Write-Host "✅ Both servers starting up!" -ForegroundColor Green
Write-Host "   Backend API:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "   Frontend App: http://localhost:3000" -ForegroundColor Cyan
Write-Host "   API Docs:     http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop both servers." -ForegroundColor Gray
Write-Host ""

# Stream output from both jobs
try {
    while ($true) {
        Receive-Job $backendJob  | ForEach-Object { Write-Host "[BACKEND]  $_" -ForegroundColor Blue }
        Receive-Job $frontendJob | ForEach-Object { Write-Host "[FRONTEND] $_" -ForegroundColor Green }
        Start-Sleep -Milliseconds 500
    }
} finally {
    Stop-Job $backendJob, $frontendJob
    Remove-Job $backendJob, $frontendJob
    Write-Host "Servers stopped." -ForegroundColor Gray
}
