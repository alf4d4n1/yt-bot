@echo off
title YT-Content-Factory :: DAEMON (Full Auto)
cd /d "D:\ALL BOTT\YT-bot-main"

echo ==========================================================
echo   YT-Content-Factory - FULL AUTO DAEMON
echo   Videos per hari : 3
echo   Jadwal tayang   : 08:00 / 14:00 / 21:00 WIB
echo   Log             : output\daemon.log
echo ==========================================================
echo.
echo   [PENTING] Tutup Chrome / browser dulu biar RAM lega.
echo   [PENTING] Jangan tutup jendela ini selama bot jalan.
echo.

"C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe" daemon.py %*

echo.
echo Daemon berhenti.
pause