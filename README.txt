SWING ANNOTATOR
===============

HOW TO START
  macOS:    double-click "Start Annotator.command"
            (first time: right-click > Open, because it is unsigned)
  Windows:  double-click "Start Annotator (Windows).bat"
  Linux:    double-click "run.sh" (choose "Run in terminal" if asked)
            After the first run it also appears in your applications menu
            as "Swing Annotator".

The first run needs internet for about a minute to install two Python
packages. After that it starts instantly. Python 3 must be installed
(on Windows, tick "Add python.exe to PATH" in the Python installer).

VIDEOS
  Put your clips in the "videos" folder. Subfolders are fine — everything
  inside is found automatically. Your originals are never modified.

A window lists every video with its annotation status. Double-click a
video to annotate it; close the list window to quit.

OUTPUT
  Everything you produce lands in the "output" folder, in a subfolder
  named after today's date. Each video you open is copied there and
  renamed like 2026-08-20_001.mp4, with its annotation next to it as
  2026-08-20_001.csv. Re-opening the same video continues the same file.
  When you're done, send back the whole "output" folder.

HOW TO ANNOTATE (two clicks per frame)
  1st click: the CLUB HEAD (red dot)
  2nd click: the GRIP / shaft end (yellow dot)
  After the second click it moves to the next frame automatically.

KEYS
  x            club NOT VISIBLE in this frame (marks it occluded, advances)
  Shift+X      "oops - the frame I JUST did was occluded" (fixes it, goes back)
  a / d        one frame back / forward     (arrow keys work too)
  A / D        ten frames back / forward
  u            undo this frame
  j            jump to the next frame that still needs annotating
  z            magnifier at the cursor, for precise clicking
  s            save now (it autosaves after every click anyway)
  q or Esc     save and go back to the video list

Progress saves automatically after every click — stop anytime, pick up later.
