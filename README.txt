GOLFWIZ SWING ANNOTATOR
=======================

HOW TO START
  macOS:    double-click "Start Annotator.command"
            (first time: right-click > Open, because it is unsigned)
  Linux:    double-click "run.sh" (choose "Run in terminal" if asked)

The first run needs internet for about a minute to install two Python
packages. After that it starts instantly. Python 3 must be installed.

VIDEOS
  Put your clips in the "videos" folder. Folders and folders-of-folders
  are fine — everything inside is found automatically. Your originals
  are never modified.

At startup you get a numbered list of every video (with how many frames
are already annotated). Type the number to open it.

HOW TO ANNOTATE (two clicks per frame)
  1st click: the CLUB HEAD (red dot)
  2nd click: the SHAFT END / grip (yellow dot)
  A green shaft line joins them and it moves to the next frame automatically.

The bar at the top shows your progress: green = annotated, blue = marked
occluded, grey = still to do, plus counts of frames done / occluded / left.

KEYS
  x            club NOT VISIBLE in this frame (marks it occluded, advances)
  u            undo this frame
  n            jump to the next frame that still needs annotating
  a / d        one frame back / forward
  v            cycle view: plain frame / motion heat overlay / heat only
               (also the VIEW button in the sidebar)
  z            magnifier at the cursor, for precise clicking
  e            export today's session (same as the EXPORT button)
  s            save now (it autosaves after every click anyway)
  q or Esc     save and quit

Progress saves automatically after every click — stop anytime, pick up later.
Annotations live in "annotations/<clip>.csv".

EXPORTING YOUR SESSION
  When you finish for the day, click the green EXPORT button (top right)
  or press "e". A zip with everything you annotated today appears in the
  "exports" folder — send that zip back.
