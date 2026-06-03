@echo off
echo =========================================
echo    Starting BirdDog Auto-Tracker...
echo =========================================
echo.

D:
cd "D:\birddog project"

.\.venv\Scripts\python.exe main.py --stream 3

echo.
echo The tracker has stopped.
pause
