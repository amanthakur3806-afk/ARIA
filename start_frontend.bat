@echo off
title ARIA - Frontend Server
cd /d "%~dp0Agent\frontend"
echo Starting Vite Frontend on http://localhost:5173 ...
call npm.cmd run dev
pause
