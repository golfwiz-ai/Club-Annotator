#!/bin/bash
# GolfWiz Annotator launcher (macOS). Double-click to start.
# First time: right-click > Open, because it is unsigned.
cd "$(dirname "$0")"
if [ -x "./GolfWizAnnotator" ]; then
    xattr -dr com.apple.quarantine ./GolfWizAnnotator 2>/dev/null
    ./GolfWizAnnotator
else
    echo "GolfWizAnnotator binary not found next to this launcher."
    echo "Put the GolfWizAnnotator file in this folder and try again."
fi
read -p "Press Enter to close..."
