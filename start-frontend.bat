@echo off
title MLB AI Stats - Frontend
echo.
echo ========================================
echo   MLB AI Stats - Frontend
echo   http://localhost:3000
echo ========================================
echo.
set PATH=D:\nodejs\node-v22.16.0-win-x64;%PATH%
cd /d D:\mlb-stats-app\frontend
node "D:\nodejs\node-v22.16.0-win-x64\node_modules\npm\bin\npm-cli.js" run dev
pause
