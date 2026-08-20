#!/bin/bash
# Launcher for the swing annotator (macOS + Linux).
# macOS: double-click "Start Annotator.command" (it runs this script).
# Linux: double-click this file (choose "Run in terminal" if asked), or run
#        ./run.sh in a terminal. First run also adds a "Swing Annotator"
#        entry to your applications menu.
cd "$(dirname "$0")" || exit 1

# A venv copied from another machine has a broken python symlink even though
# venv/bin/activate exists — so test the interpreter itself, and rebuild the
# venv if it doesn't actually work.
if ! venv/bin/python -c "import sys" >/dev/null 2>&1; then
    echo "Setting up a Python environment (needs internet, ~1 minute)..."
    rm -rf venv
    python3 -m venv venv || { echo "python3 not found - install Python 3 first"; read -r -p "Press Enter to close..."; exit 1; }
    venv/bin/pip install --quiet --upgrade pip
fi
venv/bin/python -c "import cv2, numpy" >/dev/null 2>&1 || \
    venv/bin/pip install --quiet opencv-python numpy

# Linux: install a menu/desktop entry on first run so future launches are a click
if [ "$(uname)" = "Linux" ] && [ ! -f "$HOME/.local/share/applications/swing-annotator.desktop" ]; then
    mkdir -p "$HOME/.local/share/applications"
    cat > "$HOME/.local/share/applications/swing-annotator.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Swing Annotator
Exec=$(pwd)/run.sh
Path=$(pwd)
Terminal=true
Categories=Utility;
EOF
    chmod +x "$HOME/.local/share/applications/swing-annotator.desktop"
    echo "Added 'Swing Annotator' to your applications menu."
fi

# auto-update from GitHub (anonymous, skipped silently when offline)
venv/bin/python update.py

venv/bin/python annotate.py "$@"

read -r -p "Press Enter to close..."
