@echo off
REM GolfWiz Annotator launcher (Windows). Double-click to start.
cd /d "%~dp0"
if exist GolfWizAnnotator.exe (
    GolfWizAnnotator.exe
) else (
    echo GolfWizAnnotator.exe not found next to this launcher.
)
pause
