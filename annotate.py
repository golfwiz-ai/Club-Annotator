#!/usr/bin/env python3
"""Two-click club annotator (standalone).

Each frame needs TWO clicks:
    1st click = CLUB HEAD        (red dot)
    2nd click = SHAFT END / grip (yellow dot)
A green shaft line joins them and the tool auto-advances to the next
un-annotated frame.

Videos are discovered RECURSIVELY under videos/ (subfolders welcome).
The originals are never touched. On first open, each clip is assigned an
output slot:

    output/<YYYY-MM-DD>/<YYYY-MM-DD>_<serial>.<ext>   copy of the video
    output/<YYYY-MM-DD>/<YYYY-MM-DD>_<serial>.csv    its annotation

    CSV columns: frame,head_x,head_y,grip_x,grip_y,state   state = ok|occluded

output/manifest.json remembers which source video maps to which slot, so
re-opening the same clip resumes the same CSV instead of creating a new one.

Keys:
    left click       place clubhead, then grip (auto-advance after grip)
    n / right / d    next frame            p / left / a   previous frame
    N / D            +10 frames            P / A          -10 frames
    u / backspace    undo this frame's annotation
    x                mark frame OCCLUDED (club not visible)
    X (shift-x)      mark the LAST EDITED frame occluded and return to it
    j                jump to next UN-annotated frame
    z                toggle 3x loupe at the cursor (precise clicking)
    s                save now (also autosaves on every edit and on quit)
    q / esc          quit (saves)
"""

import csv
import json
import os
import shutil
import sys
from datetime import date

import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
VID_DIR = os.path.join(HERE, "videos")
OUT_DIR = os.path.join(HERE, "output")
MANIFEST = os.path.join(OUT_DIR, "manifest.json")
VIDEO_EXTS = (".mov", ".mp4", ".avi", ".m4v")
MAX_DISP_H = 900          # fit tall phone video onto screen
LOUPE = 3                 # magnifier zoom factor
LOUPE_R = 60              # half-size (source px) of the loupe region


def find_videos():
    """All videos under videos/, any folder depth, as relative paths."""
    vids = []
    for root, _dirs, files in os.walk(VID_DIR):
        for f in files:
            if f.lower().endswith(VIDEO_EXTS) and not f.startswith("."):
                vids.append(os.path.relpath(os.path.join(root, f), VID_DIR))
    return sorted(vids)


def pick_video():
    vids = find_videos()
    if not vids:
        raise SystemExit(f"no videos found in {VID_DIR}")
    for i, v in enumerate(vids):
        print(f"  [{i}] {v}")
    s = input("clip number (or path): ").strip()
    if s.isdigit():
        return os.path.join(VID_DIR, vids[int(s)])
    return s


# ---- output slots ----------------------------------------------------
def _load_manifest():
    if os.path.exists(MANIFEST):
        with open(MANIFEST) as fh:
            return json.load(fh)
    return {}


def _save_manifest(m):
    tmp = MANIFEST + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True)
    os.replace(tmp, MANIFEST)


def assign_output(video_path):
    """Return (video_copy_path, csv_path) for this source video.

    First open: create output/<today>/, copy the video in as
    <today>_<serial>.<ext>, record the mapping in the manifest.
    Later opens: reuse the recorded slot so annotation resumes.

    manifest.json: { "<source relpath>": {"slot": "<date>/<date>_<serial>",
                                          "frames": <total or null> } }
    """
    os.makedirs(OUT_DIR, exist_ok=True)
    src_key = os.path.relpath(os.path.abspath(video_path), VID_DIR)
    manifest = _load_manifest()
    if src_key in manifest:
        stem = os.path.join(OUT_DIR, manifest[src_key]["slot"])
        ext = os.path.splitext(video_path)[1]
        return stem + ext, stem + ".csv"
    today = date.today().isoformat()
    day_dir = os.path.join(OUT_DIR, today)
    os.makedirs(day_dir, exist_ok=True)
    # next free serial within today's folder
    used = set()
    for f in os.listdir(day_dir):
        name = os.path.splitext(f)[0]
        if name.startswith(today + "_"):
            tail = name[len(today) + 1:]
            if tail.isdigit():
                used.add(int(tail))
    serial = 1
    while serial in used:
        serial += 1
    name = f"{today}_{serial:03d}"
    ext = os.path.splitext(video_path)[1]
    dst_vid = os.path.join(day_dir, name + ext)
    if not os.path.exists(dst_vid):
        print(f"copying video -> {dst_vid}")
        shutil.copy2(video_path, dst_vid)
    manifest[src_key] = {"slot": os.path.join(today, name), "frames": None}
    _save_manifest(manifest)
    return dst_vid, os.path.join(day_dir, name + ".csv")


def record_total_frames(video_path, n):
    """Store the decoder-true frame count so the picker can show progress."""
    src_key = os.path.relpath(os.path.abspath(video_path), VID_DIR)
    manifest = _load_manifest()
    if src_key in manifest and manifest[src_key].get("frames") != n:
        manifest[src_key]["frames"] = n
        _save_manifest(manifest)


def annotation_status(rel):
    """(status_text, done, total) for one videos/-relative path."""
    manifest = _load_manifest()
    entry = manifest.get(rel)
    if entry is None:
        return "not started", 0, None
    csv_path = os.path.join(OUT_DIR, entry["slot"] + ".csv")
    done = 0
    if os.path.exists(csv_path):
        with open(csv_path) as fh:
            done = max(0, sum(1 for _ in fh) - 1)      # minus header
    total = entry.get("frames")
    if done == 0:
        return "opened, 0 frames", 0, total
    if total:
        pct = 100 * done // total
        tag = "DONE" if done >= total else f"{pct}%"
        return f"{done}/{total} frames ({tag})", done, total
    return f"{done} frames", done, None


class Annotator:
    def __init__(self, path):
        self.path = path
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise SystemExit(f"cannot open {path}")
        self.N = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.W = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.H = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.sc = min(1.0, MAX_DISP_H / self.H)
        self.dw, self.dh = int(self.W * self.sc), int(self.H * self.sc)
        # ann[frame] = ("ok", hx, hy, gx, gy) or ("occluded", None...)
        self.ann = {}
        self.f = 0
        self.pending_head = None      # first click held until the grip click
        self.loupe = False
        self.mouse = (0, 0)
        self._jpegs = None            # one-shot sequential decode, held as JPEG
        self._raw_cache = (-1, None)  # last full-res frame, decoded from JPEG
        self._disp_cache = (-1, None) # last display-size frame
        _vid_copy, self.csv_path = assign_output(path)
        self.clip = os.path.splitext(os.path.basename(self.csv_path))[0]
        self._load()

    # ---- persistence -------------------------------------------------
    def _load(self):
        if not os.path.exists(self.csv_path):
            return
        with open(self.csv_path) as fh:
            for row in csv.DictReader(fh):
                fr = int(row["frame"])
                if row["state"] == "occluded":
                    self.ann[fr] = ("occluded", None, None, None, None)
                else:
                    self.ann[fr] = ("ok", float(row["head_x"]), float(row["head_y"]),
                                    float(row["grip_x"]), float(row["grip_y"]))
        print(f"resumed {len(self.ann)} annotated frames from {self.csv_path}")
        nxt = self._next_unannotated(0)
        self.f = nxt if nxt is not None else 0

    def _save(self):
        tmp = self.csv_path + ".tmp"
        with open(tmp, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["frame", "head_x", "head_y", "grip_x", "grip_y", "state"])
            for fr in sorted(self.ann):
                st, hx, hy, gx, gy = self.ann[fr]
                if st == "occluded":
                    w.writerow([fr, "", "", "", "", "occluded"])
                else:
                    w.writerow([fr, f"{hx:.1f}", f"{hy:.1f}",
                                f"{gx:.1f}", f"{gy:.1f}", "ok"])
        os.replace(tmp, self.csv_path)

    # ---- frames ------------------------------------------------------
    # NEVER SEEK. cap.set(CAP_PROP_POS_FRAMES) is unreliable on these files:
    # the decoded frame can be one early/late or garbage, which silently shifts
    # every annotation. All frames are decoded ONCE, sequentially — the only
    # mode the decoder gets right. Raw BGR frames cost ~8 MB each (several GB
    # per clip, enough to push a 16 GB machine into swap, stalling the GUI), so
    # frames are held JPEG-encoded (~0.2 MB, q=98, visually lossless at
    # annotation zoom) and decoded on demand, with the current frame cached.
    def _decode_all(self):
        if self._jpegs is not None:
            return
        print("decoding all frames sequentially (no seeking) ...")
        self._jpegs = []
        cap = cv2.VideoCapture(self.path)
        while True:
            ok, img = cap.read()
            if not ok:
                break
            ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 98])
            self._jpegs.append(buf if ok else None)
        cap.release()
        self.N = len(self._jpegs)          # decoder truth beats the header count
        record_total_frames(self.path, self.N)
        print(f"decoded {self.N} frames")

    def _get(self, fr):
        self._decode_all()
        if self._raw_cache[0] == fr:
            return self._raw_cache[1]
        img = None
        if 0 <= fr < len(self._jpegs) and self._jpegs[fr] is not None:
            img = cv2.imdecode(self._jpegs[fr], cv2.IMREAD_COLOR)
        self._raw_cache = (fr, img)
        return img

    def _get_disp(self, fr):
        """Display-size frame, cached so the 50 Hz redraw does no work."""
        if self._disp_cache[0] == fr:
            return self._disp_cache[1]
        img = self._get(fr)
        disp = cv2.resize(img, (self.dw, self.dh)) if img is not None else self._blank()
        self._disp_cache = (fr, disp)
        return disp

    def _next_unannotated(self, start):
        for fr in range(start, self.N):
            if fr not in self.ann:
                return fr
        return None

    # ---- mouse -------------------------------------------------------
    def on_mouse(self, event, x, y, flags, _):
        self.mouse = (x, y)
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        ox, oy = x / self.sc, y / self.sc                # -> original px
        if self.pending_head is None:
            self.pending_head = (ox, oy)                 # first click = head
        else:
            hx, hy = self.pending_head
            self.ann[self.f] = ("ok", hx, hy, ox, oy)    # second = grip
            self.last_edit = self.f
            self.pending_head = None
            self._save()
            nxt = self._next_unannotated(self.f + 1)
            self.f = nxt if nxt is not None else min(self.f + 1, self.N - 1)

    # ---- render ------------------------------------------------------
    def draw(self):
        disp = self._get_disp(self.f).copy()
        a = self.ann.get(self.f)
        if a and a[0] == "ok":
            hx, hy, gx, gy = (a[1] * self.sc, a[2] * self.sc,
                              a[3] * self.sc, a[4] * self.sc)
            cv2.line(disp, (int(gx), int(gy)), (int(hx), int(hy)), (0, 255, 0), 2)
            cv2.circle(disp, (int(gx), int(gy)), 6, (0, 220, 255), -1)   # grip
            cv2.circle(disp, (int(hx), int(hy)), 6, (0, 0, 255), -1)     # head
        if self.pending_head is not None:
            px, py = self.pending_head[0] * self.sc, self.pending_head[1] * self.sc
            cv2.circle(disp, (int(px), int(py)), 6, (0, 0, 255), 2)
            # live rubber-band shaft line to the cursor
            cv2.line(disp, (int(px), int(py)),
                     (int(self.mouse[0]), int(self.mouse[1])), (0, 180, 0), 1)
        self._hud(disp, a)
        if self.loupe:
            self._draw_loupe(self._get(self.f), disp)
        cv2.imshow("annotate", disp)

    def _blank(self):
        import numpy as np
        return np.zeros((self.dh, self.dw, 3), "uint8")

    def _hud(self, disp, a):
        done = len(self.ann)
        if self.pending_head is not None:
            step = "click SHAFT END (yellow)"
        elif a and a[0] == "ok":
            step = "done - d:next  u:undo"
        elif a and a[0] == "occluded":
            step = "OCCLUDED - u:undo"
        else:
            step = "click CLUB HEAD (red)   x:occluded  [X = last frame occluded]"
        bar = f"{self.clip}  frame {self.f}/{self.N-1}  annotated {done}/{self.N}  | {step}"
        cv2.rectangle(disp, (0, 0), (self.dw, 26), (0, 0, 0), -1)
        cv2.putText(disp, bar, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (255, 255, 255), 1, cv2.LINE_AA)

    def _draw_loupe(self, img, disp):
        if img is None:
            return
        ox, oy = int(self.mouse[0] / self.sc), int(self.mouse[1] / self.sc)
        x0, y0 = max(ox - LOUPE_R, 0), max(oy - LOUPE_R, 0)
        x1, y1 = min(ox + LOUPE_R, self.W), min(oy + LOUPE_R, self.H)
        crop = img[y0:y1, x0:x1]
        if crop.size == 0:
            return
        z = cv2.resize(crop, (crop.shape[1] * LOUPE, crop.shape[0] * LOUPE),
                       interpolation=cv2.INTER_NEAREST)
        cv2.drawMarker(z, ((ox - x0) * LOUPE, (oy - y0) * LOUPE),
                       (0, 255, 0), cv2.MARKER_CROSS, 20, 1)
        h, w = z.shape[:2]
        disp[26:26 + h, self.dw - w:self.dw] = z         # top-right inset

    # ---- loop --------------------------------------------------------
    def run(self):
        self._decode_all()            # up front, so the window never opens frozen
        if self.f >= self.N:
            self.f = 0
        cv2.namedWindow("annotate")
        cv2.setMouseCallback("annotate", self.on_mouse)
        while True:
            self.draw()
            k = cv2.waitKey(20) & 0xFF
            if k in (ord("q"), 27):
                break
            elif k in (ord("n"), ord("d"), 83):
                self.f = min(self.f + 1, self.N - 1); self.pending_head = None
            elif k in (ord("p"), ord("a"), 81):
                self.f = max(self.f - 1, 0); self.pending_head = None
            elif k in (ord("N"), ord("D")):
                self.f = min(self.f + 10, self.N - 1); self.pending_head = None
            elif k in (ord("P"), ord("A")):
                self.f = max(self.f - 10, 0); self.pending_head = None
            elif k in (ord("u"), 8):
                self.ann.pop(self.f, None); self.pending_head = None; self._save()
            elif k == ord("x"):
                self.ann[self.f] = ("occluded", None, None, None, None)
                self.last_edit = self.f
                self.pending_head = None; self._save()
                nxt = self._next_unannotated(self.f + 1)
                self.f = nxt if nxt is not None else self.f
            elif k == ord("X"):
                # THE MISATTRIBUTION FIX. Saving a frame auto-jumps to the next
                # unannotated frame, so an `x` meant for the frame you JUST
                # annotated lands on the new frame instead. Shif t-X marks the
                # LAST EDITED frame occluded and returns there.
                le = getattr(self, "last_edit", None)
                if le is not None:
                    self.ann[le] = ("occluded", None, None, None, None)
                    self.f = le
                    self.pending_head = None; self._save()
            elif k == ord("j"):
                nxt = self._next_unannotated(self.f + 1)
                if nxt is not None:
                    self.f = nxt
            elif k == ord("z"):
                self.loupe = not self.loupe
            elif k == ord("s"):
                self._save()
        self._save()
        cv2.destroyAllWindows()
        print(f"saved {len(self.ann)} frames -> {self.csv_path}")


# ---- GUI picker ------------------------------------------------------
def gui_pick_video():
    """Tk window listing every video with its annotation status.

    Returns the chosen video's absolute path, or None if the window is
    closed. Falls back to the terminal menu if tkinter is unavailable.
    """
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        return pick_video()

    vids = find_videos()
    if not vids:
        raise SystemExit(f"no videos found in {VID_DIR}")

    root = tk.Tk()
    root.title("Swing Annotator - pick a video")
    root.geometry("640x420")
    tk.Label(root, text="Double-click a video to annotate it. "
                        "Close this window to quit.").pack(pady=(8, 4))
    cols = ("video", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", selectmode="browse")
    tree.heading("video", text="Video")
    tree.heading("status", text="Annotation status")
    tree.column("video", width=340)
    tree.column("status", width=260)
    sb = ttk.Scrollbar(root, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
    sb.pack(side="left", fill="y", pady=8)

    def refresh():
        tree.delete(*tree.get_children())
        for v in vids:
            status, _done, _total = annotation_status(v)
            tree.insert("", "end", iid=v, values=(v, status))
    refresh()

    chosen = []

    def on_open(_event=None):
        sel = tree.selection()
        if sel:
            chosen.append(os.path.join(VID_DIR, sel[0]))
            root.destroy()

    tree.bind("<Double-1>", on_open)
    tree.bind("<Return>", on_open)
    tk.Button(root, text="Annotate selected", command=on_open).pack(
        side="top", pady=8, padx=8)
    root.mainloop()
    return chosen[0] if chosen else None


def main():
    if len(sys.argv) > 1 and sys.argv[1] != "--cli":
        Annotator(sys.argv[1]).run()
        return
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        Annotator(pick_video()).run()
        return
    # GUI loop: picker -> annotate -> back to picker (with fresh status)
    while True:
        vid = gui_pick_video()
        if vid is None:
            break
        Annotator(vid).run()


if __name__ == "__main__":
    print(__doc__)
    main()
