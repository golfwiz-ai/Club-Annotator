#!/bin/bash
# GolfWiz Annotator launcher (macOS). Double-click to start.
# First time: right-click > Open, because it is unsigned.
cd "$(dirname "$0")"
if [ -x "./GolfWizAnnotator" ]; then
    xattr -dr com.apple.quarantine ./GolfWizAnnotator 2>/dev/null
    # Detach the app, then close this Terminal window so only the GUI remains.
    nohup ./GolfWizAnnotator >/dev/null 2>&1 &
    disown
    osascript -e 'tell application "Terminal" to close front window' >/dev/null 2>&1 &
    exit 0
else
    echo "GolfWizAnnotator binary not found next to this launcher."
    echo "Put the GolfWizAnnotator file in this folder and try again."
    read -p "Press Enter to close..."
fi
