@echo off
REM GolfWiz Annotator launcher (Windows). Double-click to start.
REM The app is built windowless, so no console appears at all.
cd /d "%~dp0"
if exist GolfWizAnnotator.exe (
    start "" GolfWizAnnotator.exe
) else (
    echo GolfWizAnnotator.exe not found next to this launcher.
    pause
)
