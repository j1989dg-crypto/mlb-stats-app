@echo off
title MLB AI Stats - Stopping...
echo.
echo ==========================================
echo   MLB AI Stats - Stopping Servers
echo ==========================================
echo.
echo Stopping backend server (Port 8000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" 2^>nul') do (
    taskkill /F /PID %%a 2>nul
    echo Stopped process %%a
)
echo.
echo Stopping frontend server (Port 3000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000" 2^>nul') do (
    taskkill /F /PID %%a 2>nul
    echo Stopped process %%a
)
echo.
echo ==========================================
echo   Both servers stopped successfully.
echo ==========================================
echo.
timeout /t 3
