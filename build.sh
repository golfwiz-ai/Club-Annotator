#!/bin/bash
# Build the annotator into a single self-contained binary (macOS / Ubuntu).
# Run this ON the OS you are building FOR — PyInstaller cannot cross-compile.
# Output: dist/GolfWizAnnotator  (plus the launcher files to ship alongside it)
set -e
cd "$(dirname "$0")"

if [ ! -f "venv/bin/activate" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet opencv-python numpy cryptography pyinstaller

pyinstaller --onefile --noconfirm --clean \
    --name GolfWizAnnotator \
    annotate.py

echo
echo "Built: dist/GolfWizAnnotator"
echo "Ship the binary together with:  Start Annotator.command (macOS)"
echo "or run-annotator.sh (Ubuntu), plus an empty videos/ folder."
