@echo off
title MLB AI Stats - Starting...
echo.
echo ==========================================
echo   MLB AI Stats - Full Stack Launcher
echo   Starting Backend + Frontend...
echo ==========================================
echo.

REM Kill any existing processes on ports 8000/3000
echo Stopping any existing servers...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" 2^>nul') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000" 2^>nul') do taskkill /F /PID %%a 2>nul
timeout /t 2 /nobreak >nul

REM Start backend in a new window
echo Starting Backend API...
start "MLB Backend (Port 8000)" cmd /k "title MLB Backend && set PYTHONPATH=D:\mlb-stats-app\site-packages && set TEMP=D:\tmp && set TMP=D:\tmp && set PYTHONIOENCODING=utf-8 && cd /d D:\mlb-stats-app\backend && D:\mlb-stats-app\venv\Scripts\python.exe -W ignore main.py"

REM Wait for backend to start
echo Waiting for backend to initialize (8 seconds)...
timeout /t 8 /nobreak >nul

REM Start frontend in a new window
echo Starting Frontend...
start "MLB Frontend (Port 3000)" cmd /k "title MLB Frontend && set PATH=D:\nodejs\node-v22.16.0-win-x64;%PATH% && cd /d D:\mlb-stats-app\frontend && node D:\nodejs\node-v22.16.0-win-x64\node_modules\npm\bin\npm-cli.js run dev"

REM Wait a moment then open browser
echo Waiting for frontend to compile (10 seconds)...
timeout /t 10 /nobreak >nul

echo.
echo ==========================================
echo   App starting at http://localhost:3000
echo ==========================================
echo.
start "" "http://localhost:3000"

echo Both servers are running in separate windows.
echo Close those windows to stop the servers.
pause
