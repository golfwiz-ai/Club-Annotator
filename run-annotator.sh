#!/bin/bash
# GolfWiz Annotator launcher (Ubuntu/Linux). Double-click and choose
# "Run in terminal", or run from a terminal: ./run-annotator.sh
cd "$(dirname "$0")"
if [ -x "./GolfWizAnnotator" ]; then
    # Detach so the terminal window can close; the GUI keeps running.
    nohup ./GolfWizAnnotator >/dev/null 2>&1 &
    disown
    exit 0
else
    echo "GolfWizAnnotator binary not found next to this launcher."
    read -p "Press Enter to close..."
fi
