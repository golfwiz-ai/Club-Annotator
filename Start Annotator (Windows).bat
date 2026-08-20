@echo off
rem Windows launcher for the swing annotator. Double-click me.
rem First run creates a Python environment (needs internet, ~1 minute);
rem after that it just starts the app.
cd /d "%~dp0"

rem Rebuild the venv if its python doesn't actually work (e.g. copied
rem from another machine or a different OS).
venv\Scripts\python.exe -c "import sys" >nul 2>&1
if errorlevel 1 (
    echo Setting up a Python environment, this takes about a minute...
    if exist venv rmdir /s /q venv
    py -3 -m venv venv 2>nul || python -m venv venv
    if not exist venv\Scripts\python.exe (
        echo Python 3 was not found. Install it from https://www.python.org/downloads/
        echo IMPORTANT: tick "Add python.exe to PATH" in the installer.
        pause
        exit /b 1
    )
    venv\Scripts\python.exe -m pip install --quiet --upgrade pip
)
venv\Scripts\python.exe -c "import cv2, numpy" >nul 2>&1 || venv\Scripts\python.exe -m pip install --quiet opencv-python numpy

rem auto-update from GitHub (anonymous, skipped silently when offline)
venv\Scripts\python.exe update.py

venv\Scripts\python.exe annotate.py %*
pause
