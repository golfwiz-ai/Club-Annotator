#!/bin/bash
# GolfWiz Annotator launcher (Ubuntu/Linux). Double-click and choose
# "Run in terminal", or run from a terminal: ./run-annotator.sh
cd "$(dirname "$0")"
if [ -x "./GolfWizAnnotator" ]; then
    ./GolfWizAnnotator
else
    echo "GolfWizAnnotator binary not found next to this launcher."
fi
read -p "Press Enter to close..."
