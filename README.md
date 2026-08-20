<p align="center">
  <img src="https://golfwiz-assets.s3.us-east-1.amazonaws.com/logo.webp" alt="GolfWiz" width="160">
</p>

<h1 align="center">Club-Annotator</h1>

<p align="center"><b>GolfWiz's internal annotation tool</b> — ground-truth labelling of golf-club positions in swing videos, built for the GolfWiz swing-tracing pipeline.</p>

---

## What it is

Club-Annotator is a standalone desktop app used internally at GolfWiz to
produce frame-by-frame ground truth for club tracking. For every frame of a
swing video the annotator records two points — the **club head** and the
**grip (shaft end)** — which together define the club's position and shaft
line. These annotations are used to benchmark and train the GolfWiz swing
tracer.

It is deliberately minimal: **two clicks per frame**, automatic advance,
automatic saving, and it runs on macOS, Windows, and Linux with nothing
pre-installed except Python 3.

## Getting started

1. Download this repository (green **Code** button → *Download ZIP*) and
   unzip it anywhere — no GitHub account or git needed.
2. Make sure Python 3 is installed
   ([python.org](https://www.python.org/downloads/); on Windows tick
   *"Add python.exe to PATH"* in the installer).
3. Drop your swing clips into the `videos/` folder. Subfolders are fine —
   everything inside is discovered automatically, and your original files
   are never modified.
4. Double-click the launcher for your OS:

   | OS | Launcher |
   |---|---|
   | macOS | `Start Annotator.command` (first time: right-click → Open, it's unsigned) |
   | Windows | `Start Annotator (Windows).bat` |
   | Linux | `run.sh` (choose *"Run in terminal"* if asked; adds a **Swing Annotator** menu entry after the first run) |

   The first launch takes about a minute: it creates a private Python
   environment and installs OpenCV. Every launch after that is instant.

## Using the app

A picker window lists every video with its annotation status
(*not started*, *143/280 frames (51%)*, *DONE*). Double-click a video to
open it.

For each frame:

1. **1st click — club head** (red dot)
2. **2nd click — grip / shaft end** (yellow dot)

A green shaft line joins the two points and the app advances to the next
un-annotated frame by itself. A live rubber-band line follows the cursor
between the two clicks.

### Keys

| Key | Action |
|---|---|
| `x` | club **not visible** this frame → mark occluded and advance |
| `Shift+X` | *"the frame I just did was occluded"* — fixes the last edited frame and returns to it |
| `a` / `d` (or arrows) | one frame back / forward |
| `A` / `D` | ten frames back / forward |
| `u` / backspace | undo this frame |
| `j` | jump to the next frame that still needs annotating |
| `z` | 3× magnifier at the cursor for precise clicking |
| `s` | save now (it autosaves after every click anyway) |
| `q` / Esc | save and return to the video list |

Progress saves after **every** click — stop anytime, reopen the same video
later, and it resumes exactly where you left off.

## Output

Everything lands in an `output/` folder, organised by date:

```
output/
└── 2026-08-20/
    ├── 2026-08-20_001.mp4    ← copy of the source video
    ├── 2026-08-20_001.csv    ← its annotation
    ├── 2026-08-20_002.mp4
    └── 2026-08-20_002.csv
└── manifest.json             ← maps each source video to its output slot
```

Each video you open is assigned a `date_serial` slot once and keeps it
forever (the manifest remembers the mapping), so reopening a clip continues
the same CSV rather than creating a duplicate.

The CSV format matches the GolfWiz benchmark harness exactly:

```
frame,head_x,head_y,grip_x,grip_y,state
12,655.0,1226.0,760.0,1057.0,ok
13,,,,,occluded
```

Coordinates are pixels at the **original video resolution**; `state` is
`ok` or `occluded`. When you're done, send back the whole `output/` folder.

## Auto-update

On every start the app checks this repository's `main` branch over plain
HTTPS (anonymously — no git or GitHub login on the user's machine) and
replaces itself with the latest version if one exists. Your `videos/`,
`output/`, and `annotations/` folders are never touched by an update. If
you're offline, it simply starts the version you have.

## Accuracy notes (why it works the way it does)

- **No seeking.** Video decoders frequently return the wrong frame when
  seeking, which silently shifts every annotation. The app decodes each
  clip once, sequentially, and keeps frames in memory JPEG-compressed —
  frame-exact and light on RAM.
- **Atomic saves.** CSVs are written to a temp file and swapped in, so a
  crash can never corrupt an annotation file.
- **`Shift+X`.** After the auto-advance, an `x` meant for the frame you
  *just* annotated would land on the next frame; `Shift+X` exists so the
  correction hits the right one.

---

<p align="center">© GolfWiz — internal use. Annotations, videos, and all user data stay local and are never committed to this repository.</p>
