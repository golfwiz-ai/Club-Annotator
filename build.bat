@echo off
REM Build the annotator into a single self-contained .exe (run ON Windows).
REM Output: dist\GolfWizAnnotator.exe
cd /d "%~dp0"

if not exist venv\Scripts\activate.bat (
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install --quiet --upgrade pip
pip install --quiet opencv-python numpy cryptography pyinstaller

pyinstaller --onefile --noconfirm --clean --name GolfWizAnnotator annotate.py

echo.
echo Built: dist\GolfWizAnnotator.exe
echo Ship it with "Start Annotator (Windows).bat" and an empty videos folder.
pause
