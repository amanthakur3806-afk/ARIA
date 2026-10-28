@echo off
title ARIA - All-In-One Launcher
echo ======================================================================
echo                  Starting ARIA (Backend + Frontend)
echo ======================================================================
echo.

echo [1/2] Launching ARIA Backend Server on http://127.0.0.1:8000 ...
start "ARIA Backend Server (FastAPI + RAG + MCP)" cmd /k "cd /d "%~dp0Agent\backend" && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo [2/2] Launching ARIA Frontend UI on http://localhost:5173 ...
timeout /t 2 /nobreak >nul
start "ARIA Frontend (Vite + React)" cmd /k "cd /d "%~dp0Agent\frontend" && call npm.cmd run dev"

echo.
echo ======================================================================
echo Both services are launching in separate windows!
echo Once Vite is ready, open: http://localhost:5173
echo ======================================================================
echo.
pause
