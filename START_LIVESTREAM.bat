@echo off
title YT-Content-Factory :: LIVE STREAM 24/7
cd /d "D:\ALL BOTT\YT-bot-main"

echo.
echo ============================================================
echo   COZY MOOD LOUNGE - LIVE STREAM 24/7
echo   Visual : 5 video overlay (rotasi tiap 25 menit)
echo   Audio  : Musik 432Hz + Ambience per formula
echo   Mode   : LANGSUNG STREAM - TANPA RENDER
echo ============================================================
echo.

"C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe" scripts\live_streamer.py

echo.
pause
