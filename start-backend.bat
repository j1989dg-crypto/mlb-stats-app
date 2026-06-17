@echo off
title MLB AI Stats - Backend API
echo.
echo ========================================
echo   MLB AI Stats - Backend API
echo   http://localhost:8000
echo   http://localhost:8000/docs
echo ========================================
echo.
set PYTHONPATH=D:\mlb-stats-app\backend
set TEMP=D:\tmp
set TMP=D:\tmp
set PYTHONIOENCODING=utf-8
cd /d D:\mlb-stats-app\backend
D:\mlb-stats-app\venv313\Scripts\python.exe -W ignore main.py
pause
