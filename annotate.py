#!/usr/bin/env python3
"""GolfWiz two-click club annotator.

Each frame needs TWO clicks:
    1st click = CLUB HEAD          (red dot)
    2nd click = SHAFT END / grip   (yellow dot)
A green shaft line joins them and the tool auto-advances to the next frame.

Output:
    annotations/<CLIP>.csv
    frame,head_x,head_y,grip_x,grip_y,state,ts     state = ok | occluded
(older CSVs without the ts column load fine and are upgraded on save)

Videos: drop files, a folder of videos, or folders-of-folders into videos/ —
everything is found automatically.

Keys:
    left click   place head, then shaft end (auto-advance after 2nd click)
    x            mark frame OCCLUDED (club not visible) and advance
    u            undo this frame's annotation
    n            jump to next un-annotated frame
    a / d        previous / next frame
    v            cycle view: frame / heat overlay / heat only
    z            toggle 3x loupe at the cursor (precise clicking)
    e            export today's session (also the EXPORT button)
    s            save now (autosaves on every edit anyway)
    q / ESC      save and quit
"""

import csv
import glob
import hashlib
import json
import os
import sys
import time
import zipfile
from datetime import datetime, date

import cv2
import numpy as np

# In a windowed (no-console) build stdout/stderr are None; keep print() safe.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# When frozen by PyInstaller, __file__ lives in a temp extraction dir —
# anchor all data folders next to the executable instead.
if getattr(sys, "frozen", False):
    HERE = os.path.dirname(os.path.abspath(sys.executable))
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
ANN_DIR = os.path.join(HERE, "annotations")
VID_DIR = os.path.join(HERE, "videos")
EXPORT_DIR = os.path.join(HERE, "exports")
AUDIT_PATH = os.path.join(ANN_DIR, ".audit.log")
MAX_DISP_H = 820
LOUPE = 3
LOUPE_R = 60
PAD = 14                  # border padding around the video
HDR = 64                  # header height (title + stats + progress strip)
SIDEBAR = 240             # right sidebar width (controls + buttons)
VID_EXTS = (".mov", ".mp4", ".avi", ".m4v", ".mkv")

# heat map (3-frame intersection) — see heatmap spec / combined_tracer.py
HEAT_HOT = 25.0
HEAT_DOWNSCALE = 2.0
VIEW_MODES = ("FRAME", "OVERLAY", "HEAT ONLY")

BG = (28, 26, 24)         # window chrome
PANEL = (40, 38, 35)      # sidebar panel

# Audit-trail encryption PUBLIC key. This can only ENCRYPT: the matching
# private key (which alone can decrypt exported audit files) exists only on
# the project owner's machine and is never distributed or committed.
_PUB_PEM = b"""-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAhY11P6zShn1nbgzScZkt
RUIHR3R3G+Vcq5hMOABauDlXnC7PhGniIXOe/t8teQekbeoBYnH+0NDkSo6Id1GE
w6AuMkbrBtTGns+F1x5stqv+Hp73lX4wXeDsTnrh176OwVJR14VA6Vp9Krm61SkY
vIlsyJO+rn8X//SFFua8lwIWTJzCuxA6RN7L/ZRgh+DcmAJwAKw9wH7cV2XsFcjv
KdQbOLrs4SklAw79LobOIGJMXVeSYLSdVxBlLpVetVWwy2K0T6boTDx7NRWYhWgU
XK8+eXNJ2QQ99gWLgh9wRAlIIjZGKXSNEVyZCLZ5+irPPWO52T8VCqn2tlDHQ2k9
9ZfDfagrQFb+d9AvmLM6xVG+e6T7PaKoxTdRLrvoQZOW1Y9NOauAHYn+HojJU8M9
p7EYnUQwOJyjFiXZT3rHsEoTqGUIFkA5o0c6eL4wJiavcyW4hY1hghF56MaG1cKl
DWhhdCCbGG7E3TVWQkqRjIDb/vIQuTg009uA8DfnW6YH6JLUTEwUcnMMj6GspZzd
HrbXfX3zG7pcz9krrvn2cMfN/M8utX2pzga5OwB/VAOsTaNpwhpBCnoBKPmWoXbO
L19cBrxqgshszZankxrWfNyxpKa5oJdlx0FAWrF+GZSsgRM67/mkboIe3pBBRBjm
fL59cC1tQpgpV3S/nrkIwSUCAwEAAQ==
-----END PUBLIC KEY-----
"""

SIDEBAR_KEYS = [
    ("CONTROLS", None),
    ("click 1", "club head"),
    ("click 2", "shaft end"),
    ("x", "mark occluded"),
    ("u", "undo frame"),
    ("n", "next un-annotated"),
    ("a / d", "prev / next frame"),
    ("v", "cycle view"),
    ("z", "magnifier loupe"),
    ("e", "export session"),
    ("s", "save now"),
    ("q / esc", "save and quit"),
]


# ---------------------------------------------------------------- audit trail
def _now_iso():
    return datetime.now().isoformat(timespec="milliseconds")


def _audit_last_mac():
    try:
        with open(AUDIT_PATH, "rb") as fh:
            lines = fh.read().splitlines()
        if lines:
            return json.loads(lines[-1])["mac"]
    except (OSError, ValueError, KeyError):
        pass
    return ""


def audit_append(clip, frame, action, data):
    """Append one hash-chained record; any later edit breaks the chain."""
    rec = {"ts": _now_iso(), "clip": clip, "frame": frame,
           "action": action, "data": data, "prev": _audit_last_mac()}
    payload = json.dumps(rec, sort_keys=True, separators=(",", ":"))
    rec["mac"] = hashlib.sha256(payload.encode()).hexdigest()
    with open(AUDIT_PATH, "a") as fh:
        fh.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")


def encrypt_bytes(data):
    """Hybrid RSA-OAEP + AES-GCM: readable only with the owner's private key.
    Layout: len(wrapped_key):4 | wrapped_key | nonce:12 | ciphertext+tag"""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    pub = serialization.load_pem_public_key(_PUB_PEM)
    aes_key = os.urandom(32)
    nonce = os.urandom(12)
    ct = AESGCM(aes_key).encrypt(nonce, data, None)
    wrapped = pub.encrypt(aes_key, padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(), label=None))
    return len(wrapped).to_bytes(4, "big") + wrapped + nonce + ct


# ---------------------------------------------------------------- heat maps
def _pair_gray(frame_bgr, downscale=HEAT_DOWNSCALE):
    fx = 1.0 / downscale
    small = cv2.resize(frame_bgr, None, fx=fx, fy=fx, interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)


def registered_pair_heat(prev_bgr, curr_bgr, prev_gray=None):
    """Half-res diff of two frames with global camera motion compensated out."""
    cv2.setRNGSeed(1234)                      # RANSAC determinism — do not remove
    g0 = prev_gray if prev_gray is not None else _pair_gray(prev_bgr)
    g1 = _pair_gray(curr_bgr)
    try:
        pts0 = cv2.goodFeaturesToTrack(g0, maxCorners=200, qualityLevel=0.01,
                                       minDistance=10)
        if pts0 is not None and len(pts0) >= 12:
            pts1, st, _ = cv2.calcOpticalFlowPyrLK(g0, g1, pts0, None)
            ok = st.reshape(-1) == 1
            if int(ok.sum()) >= 12:
                M, _ = cv2.estimateAffinePartial2D(
                    pts0[ok], pts1[ok], method=cv2.RANSAC,
                    ransacReprojThreshold=2.0)
                if M is not None:
                    g0 = cv2.warpAffine(g0, M, (g1.shape[1], g1.shape[0]),
                                        flags=cv2.INTER_LINEAR,
                                        borderMode=cv2.BORDER_REPLICATE)
    except cv2.error:
        pass                                   # unregistered fallback
    return cv2.absdiff(g0, g1), g1


# ---------------------------------------------------------------- video picker
def find_videos():
    vids = []
    for root, _dirs, files in os.walk(VID_DIR):
        for f in sorted(files):
            if f.lower().endswith(VID_EXTS) and not f.startswith("."):
                vids.append(os.path.join(root, f))
    return sorted(vids)


def clip_id(path):
    rel = os.path.relpath(path, VID_DIR)
    if rel.startswith(".."):                       # video outside videos/
        rel = os.path.basename(path)
    return os.path.splitext(rel)[0].replace(os.sep, "__")


def pick_video():
    os.makedirs(VID_DIR, exist_ok=True)
    vids = find_videos()
    if not vids:
        raise SystemExit(f"no videos found in {VID_DIR} (subfolders are scanned too)")
    for i, v in enumerate(vids):
        p = os.path.join(ANN_DIR, f"{clip_id(v)}.csv")
        n = 0
        if os.path.exists(p):
            with open(p) as fh:
                n = max(0, sum(1 for _ in fh) - 1)
        mark = f"  ({n} annotated)" if n else ""
        print(f"  [{i}] {os.path.relpath(v, VID_DIR)}{mark}")
    s = input("clip number (or path): ").strip()
    if s.isdigit():
        return vids[int(s)]
    return s


# ---------------------------------------------------------------- export
def export_session():
    """Zip everything annotated today (since the day's first annotation)."""
    today = date.today().isoformat()
    os.makedirs(EXPORT_DIR, exist_ok=True)
    out = os.path.join(EXPORT_DIR,
                       f"session_{today}_{datetime.now().strftime('%H%M%S')}.zip")
    header = ["frame", "head_x", "head_y", "grip_x", "grip_y", "state", "ts"]
    n_clips = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for csvf in sorted(glob.glob(os.path.join(ANN_DIR, "*.csv"))):
            with open(csvf) as fh:
                rows = [r for r in csv.DictReader(fh)
                        if r.get("ts", "").startswith(today)]
            if not rows:
                continue
            n_clips += 1
            lines = [",".join(header)]
            for r in rows:
                lines.append(",".join(r.get(c, "") for c in header))
            zf.writestr(os.path.basename(csvf), "\n".join(lines) + "\n")
        if os.path.exists(AUDIT_PATH):
            with open(AUDIT_PATH, "rb") as fh:
                zf.writestr("session.audit.enc", encrypt_bytes(fh.read()))
    if n_clips == 0:
        os.remove(out)
        return None
    return out


# ---------------------------------------------------------------- annotator
class Annotator:
    def __init__(self, path):
        self.path = path
        self.clip = clip_id(path)
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise SystemExit(f"cannot open {path}")
        self.N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        self.sc = min(1.0, MAX_DISP_H / self.H)
        self.dw, self.dh = int(self.W * self.sc), int(self.H * self.sc)
        self.win_w = PAD + self.dw + PAD + SIDEBAR
        self.win_h = HDR + self.dh + PAD
        # ann[frame] = ("ok", hx, hy, gx, gy, ts) or ("occluded", None x4, ts)
        self.ann = {}
        self.f = 0
        self.pending_head = None
        self.loupe = False
        self.view = 0                 # index into VIEW_MODES
        self.mouse = (0, 0)
        self.msg = ""
        self.msg_until = 0.0
        self._all_frames = None
        self._heat = None             # heat[i] = pair diff of frames i, i+1
        os.makedirs(ANN_DIR, exist_ok=True)
        self.csv_path = os.path.join(ANN_DIR, f"{self.clip}.csv")
        self._load()

    # ---- persistence -------------------------------------------------
    def _load(self):
        if not os.path.exists(self.csv_path):
            return
        with open(self.csv_path) as fh:
            for row in csv.DictReader(fh):
                fr = int(row["frame"])
                ts = row.get("ts", "")          # older versions had no ts
                if row["state"] == "occluded":
                    self.ann[fr] = ("occluded", None, None, None, None, ts)
                else:
                    self.ann[fr] = ("ok",
                                    float(row["head_x"]), float(row["head_y"]),
                                    float(row["grip_x"]), float(row["grip_y"]), ts)
        print(f"resumed {len(self.ann)} annotated frames from {self.csv_path}")
        nxt = self._next_unannotated(0)
        self.f = nxt if nxt is not None else 0

    def _save(self):
        tmp = self.csv_path + ".tmp"
        with open(tmp, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["frame", "head_x", "head_y", "grip_x", "grip_y",
                        "state", "ts"])
            for fr in sorted(self.ann):
                st, hx, hy, gx, gy, ts = self.ann[fr]
                if st == "occluded":
                    w.writerow([fr, "", "", "", "", "occluded", ts])
                else:
                    w.writerow([fr, f"{hx:.1f}", f"{hy:.1f}",
                                f"{gx:.1f}", f"{gy:.1f}", "ok", ts])
        os.replace(tmp, self.csv_path)

    # ---- frames + heat -----------------------------------------------
    # NEVER SEEK. cap.set(CAP_PROP_POS_FRAMES) is unreliable on these files
    # (frames come back one early/late or garbage, silently shifting every
    # annotation). Decode ONCE sequentially and hold in memory.
    def _get(self, fr):
        if self._all_frames is None:
            print("decoding all frames sequentially (no seeking) ...")
            self._all_frames = []
            cap = cv2.VideoCapture(self.path)
            while True:
                ok, img = cap.read()
                if not ok:
                    break
                self._all_frames.append(img)
            cap.release()
            self.N = len(self._all_frames)
            print("computing motion heat maps ...")
            self._heat, prev_gray = [], None
            for i in range(self.N - 1):
                h, prev_gray = registered_pair_heat(
                    self._all_frames[i], self._all_frames[i + 1],
                    prev_gray=prev_gray)
                self._heat.append(h)
            print("ready")
        if 0 <= fr < len(self._all_frames):
            return self._all_frames[fr]
        return None

    def _membership(self, fr):
        """3-frame intersection map for frame fr: min(heat[fr-1], heat[fr]).
        A pixel is hot only if it moved into AND out of this frame — a
        one-frame flash cancels, a sweeping club survives. None at the ends."""
        if not self._heat or fr < 1 or fr >= len(self._heat):
            return None
        return np.minimum(self._heat[fr - 1], self._heat[fr])

    def _next_unannotated(self, start):
        for fr in range(start, self.N):
            if fr not in self.ann:
                return fr
        return None

    def _advance(self):
        nxt = self._next_unannotated(self.f + 1)
        self.f = nxt if nxt is not None else min(self.f + 1, self.N - 1)

    def _flash(self, text, secs=3.0):
        self.msg, self.msg_until = text, time.time() + secs

    # ---- layout ------------------------------------------------------
    def _sidebar_x(self):
        return PAD + self.dw + PAD

    def _export_btn_rect(self):
        x = self._sidebar_x() + 12
        return (x, self.win_h - PAD - 34, x + SIDEBAR - 36, self.win_h - PAD - 6)

    def _view_btn_rect(self):
        x = self._sidebar_x() + 12
        return (x, self.win_h - PAD - 72, x + SIDEBAR - 36, self.win_h - PAD - 44)

    # ---- mouse -------------------------------------------------------
    def on_mouse(self, event, x, y, flags, _):
        self.mouse = (x, y)
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        for rect, fn in ((self._export_btn_rect(), self._do_export),
                         (self._view_btn_rect(), self._cycle_view)):
            if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                fn()
                return
        if not (PAD <= x < PAD + self.dw and HDR <= y < HDR + self.dh):
            return                                       # clicks on chrome ignored
        ox, oy = (x - PAD) / self.sc, (y - HDR) / self.sc    # -> original px
        if self.pending_head is None:
            self.pending_head = (ox, oy)                 # 1st click = head
        else:
            hx, hy = self.pending_head
            self.ann[self.f] = ("ok", hx, hy, ox, oy, _now_iso())
            self.pending_head = None
            self._save()
            audit_append(self.clip, self.f, "annotate",
                         {"head": [round(hx, 1), round(hy, 1)],
                          "grip": [round(ox, 1), round(oy, 1)], "state": "ok"})
            self._advance()

    def _cycle_view(self):
        self.view = (self.view + 1) % len(VIEW_MODES)

    def _do_export(self):
        out = export_session()
        if out:
            audit_append(self.clip, -1, "export", {"zip": os.path.basename(out)})
            self._flash(f"exported -> exports/{os.path.basename(out)}", 5)
            print(f"session export: {out}")
        else:
            self._flash("nothing annotated today - nothing to export")

    # ---- render ------------------------------------------------------
    def _video_panel(self, img):
        """The frame under the current view mode, at display size."""
        frame = cv2.resize(img, (self.dw, self.dh)) if img is not None \
            else np.zeros((self.dh, self.dw, 3), "uint8")
        mode = VIEW_MODES[self.view]
        if mode == "FRAME":
            return frame
        m = self._membership(self.f)
        if m is None:                 # first/last frame: no map on one side
            cv2.putText(frame, "no heat map at first/last frame", (12, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2,
                        cv2.LINE_AA)
            return frame
        # INTER_NEAREST: interpolation would smear hot pixels
        big = cv2.resize(m, (self.dw, self.dh), interpolation=cv2.INTER_NEAREST)
        heat = cv2.applyColorMap(big, cv2.COLORMAP_INFERNO)
        if mode == "HEAT ONLY":
            return heat
        # OVERLAY: blend the colormap onto hot pixels only
        mask = big >= HEAT_HOT
        out = frame.copy()
        out[mask] = (0.35 * out[mask] + 0.65 * heat[mask]).astype(np.uint8)
        return out

    def draw(self):
        img = self._get(self.f)
        disp = np.zeros((self.win_h, self.win_w, 3), "uint8")
        disp[:] = BG
        disp[HDR:HDR + self.dh, PAD:PAD + self.dw] = self._video_panel(img)
        cv2.rectangle(disp, (PAD - 1, HDR - 1),
                      (PAD + self.dw, HDR + self.dh), (70, 70, 70), 1)
        a = self.ann.get(self.f)
        if a and a[0] == "ok":
            hx, hy = a[1] * self.sc + PAD, a[2] * self.sc + HDR
            gx, gy = a[3] * self.sc + PAD, a[4] * self.sc + HDR
            cv2.line(disp, (int(gx), int(gy)), (int(hx), int(hy)), (0, 255, 0), 2)
            cv2.circle(disp, (int(gx), int(gy)), 6, (0, 220, 255), -1)  # shaft end
            cv2.circle(disp, (int(hx), int(hy)), 6, (0, 0, 255), -1)    # head
        if self.pending_head is not None:
            px = self.pending_head[0] * self.sc + PAD
            py = self.pending_head[1] * self.sc + HDR
            cv2.circle(disp, (int(px), int(py)), 6, (0, 0, 255), 2)
            cv2.line(disp, (int(px), int(py)), self.mouse, (0, 180, 0), 1)
        self._hud(disp, a)
        self._sidebar(disp)
        if self.loupe:
            self._draw_loupe(img, disp)
        cv2.imshow("GolfWiz Annotator", disp)

    def _hud(self, disp, a):
        ok = sum(1 for v in self.ann.values() if v[0] == "ok")
        occ = len(self.ann) - ok
        left = self.N - len(self.ann)
        cv2.putText(disp, self.clip, (PAD, 22), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (240, 240, 240), 1, cv2.LINE_AA)
        stats = f"frame {self.f + 1}/{self.N}   done {ok}   occluded {occ}   left {left}"
        cv2.putText(disp, stats, (PAD, 44), cv2.FONT_HERSHEY_SIMPLEX,
                    0.45, (170, 170, 170), 1, cv2.LINE_AA)
        # per-frame progress strip: green=ok, blue=occluded, grey=todo
        x0s, x1s = PAD, PAD + self.dw
        y0, y1 = HDR - 10, HDR - 4
        cv2.rectangle(disp, (x0s, y0), (x1s, y1), (55, 55, 55), -1)
        span = self.dw
        for fr, v in self.ann.items():
            x = x0s + int(fr / max(1, self.N - 1) * (span - 1))
            col = (90, 200, 90) if v[0] == "ok" else (60, 140, 235)
            cv2.rectangle(disp, (x, y0),
                          (min(x + max(1, span // self.N), x1s), y1), col, -1)
        cx = x0s + int(self.f / max(1, self.N - 1) * (span - 1))
        cv2.rectangle(disp, (cx, y0 - 2), (cx + 2, y1 + 2), (255, 255, 255), -1)
        # prompt / flash message under the video
        if time.time() < self.msg_until:
            step = self.msg
        elif self.pending_head is not None:
            step = "click SHAFT END (yellow)"
        elif a and a[0] == "ok":
            step = "done - d next, u undo"
        elif a and a[0] == "occluded":
            step = "OCCLUDED - u undo"
        else:
            step = "click CLUB HEAD (red)"
        cv2.putText(disp, step, (PAD, self.win_h - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1,
                    cv2.LINE_AA)

    def _sidebar(self, disp):
        x = self._sidebar_x()
        cv2.rectangle(disp, (x, HDR - 12), (self.win_w - PAD, self.win_h - PAD),
                      PANEL, -1)
        cv2.rectangle(disp, (x, HDR - 12), (self.win_w - PAD, self.win_h - PAD),
                      (70, 70, 70), 1)
        y = HDR + 14
        for key, desc in SIDEBAR_KEYS:
            if desc is None:                               # section header
                cv2.putText(disp, key, (x + 12, y), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (140, 200, 140), 1, cv2.LINE_AA)
                y += 10
                cv2.line(disp, (x + 12, y), (self.win_w - PAD - 12, y),
                         (70, 70, 70), 1)
                y += 20
                continue
            cv2.putText(disp, key, (x + 12, y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.42, (230, 230, 230), 1, cv2.LINE_AA)
            cv2.putText(disp, desc, (x + 90, y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.42, (160, 160, 160), 1, cv2.LINE_AA)
            y += 22
        # VIEW button
        bx0, by0, bx1, by1 = self._view_btn_rect()
        cv2.rectangle(disp, (bx0, by0), (bx1, by1), (85, 70, 45), -1)
        cv2.rectangle(disp, (bx0, by0), (bx1, by1), (170, 140, 90), 1)
        cv2.putText(disp, f"VIEW: {VIEW_MODES[self.view]}", (bx0 + 12, by1 - 9),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (240, 230, 210), 1,
                    cv2.LINE_AA)
        # EXPORT button
        bx0, by0, bx1, by1 = self._export_btn_rect()
        cv2.rectangle(disp, (bx0, by0), (bx1, by1), (60, 120, 60), -1)
        cv2.rectangle(disp, (bx0, by0), (bx1, by1), (110, 200, 110), 1)
        cv2.putText(disp, "EXPORT SESSION", (bx0 + 12, by1 - 9),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (235, 255, 235), 1,
                    cv2.LINE_AA)

    def _draw_loupe(self, img, disp):
        if img is None:
            return
        mx, my = self.mouse
        ox, oy = int((mx - PAD) / self.sc), int((my - HDR) / self.sc)
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
        disp[HDR:HDR + h, PAD + self.dw - w:PAD + self.dw] = z

    # ---- loop --------------------------------------------------------
    def run(self):
        cv2.namedWindow("GolfWiz Annotator")
        cv2.setMouseCallback("GolfWiz Annotator", self.on_mouse)
        try:      # bring to front when launched detached
            cv2.setWindowProperty("GolfWiz Annotator", cv2.WND_PROP_TOPMOST, 1)
            cv2.setWindowProperty("GolfWiz Annotator", cv2.WND_PROP_TOPMOST, 0)
        except cv2.error:
            pass
        while True:
            self.draw()
            k = cv2.waitKey(20) & 0xFF
            if k in (ord("q"), 27):
                break
            elif k == ord("d"):
                self.f = min(self.f + 1, self.N - 1); self.pending_head = None
            elif k == ord("a"):
                self.f = max(self.f - 1, 0); self.pending_head = None
            elif k == ord("u"):
                if self.f in self.ann:
                    self.ann.pop(self.f)
                    audit_append(self.clip, self.f, "undo", {})
                self.pending_head = None
                self._save()
            elif k == ord("x"):
                self.ann[self.f] = ("occluded", None, None, None, None, _now_iso())
                self.pending_head = None
                self._save()
                audit_append(self.clip, self.f, "annotate", {"state": "occluded"})
                self._advance()
            elif k == ord("n"):
                nxt = self._next_unannotated(self.f + 1)
                if nxt is not None:
                    self.f = nxt
                self.pending_head = None
            elif k == ord("v"):
                self._cycle_view()
            elif k == ord("z"):
                self.loupe = not self.loupe
            elif k == ord("e"):
                self._do_export()
            elif k == ord("s"):
                self._save()
        self._save()
        cv2.destroyAllWindows()
        print(f"saved {len(self.ann)} frames -> {self.csv_path}")


def clip_stats(path):
    """(done, occluded, total_frames, last_edit 'YYYY-MM-DD HH:MM') for a video."""
    done = occ = 0
    last = ""
    p = os.path.join(ANN_DIR, f"{clip_id(path)}.csv")
    if os.path.exists(p):
        with open(p) as fh:
            for row in csv.DictReader(fh):
                if row["state"] == "occluded":
                    occ += 1
                else:
                    done += 1
                ts = row.get("ts", "")
                if ts > last:
                    last = ts
    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if cap.isOpened() else 0
    cap.release()
    last_disp = last[:16].replace("T", " ") if last else "-"
    return done, occ, total, last_disp


# ---- GUI launcher ----------------------------------------------------
def gui_pick_video():
    """Tk window listing every swing with its analytics.

    Returns the chosen video's absolute path, or None if the window is
    closed. Falls back to the terminal menu if tkinter is unavailable.
    """
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except ImportError:
        return pick_video()

    os.makedirs(VID_DIR, exist_ok=True)
    vids = find_videos()

    root = tk.Tk()
    root.title("GolfWiz Annotator")
    root.geometry("860x560")
    root.configure(bg="#1c1a18")
    # Launched detached (launcher closes the terminal), the window can appear
    # behind everything with no focus — looks like the app never opened.
    root.lift()
    root.attributes("-topmost", True)
    root.after(600, lambda: root.attributes("-topmost", False))
    try:
        root.focus_force()
    except tk.TclError:
        pass

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("Treeview", rowheight=26, font=("Helvetica", 12),
                    background="#262421", fieldbackground="#262421",
                    foreground="#e8e6e3")
    style.configure("Treeview.Heading", font=("Helvetica", 12, "bold"))

    tk.Label(root, text="GolfWiz Annotator", font=("Helvetica", 18, "bold"),
             bg="#1c1a18", fg="#e8e6e3").pack(pady=(14, 2))
    summary = tk.Label(root, font=("Helvetica", 12), bg="#1c1a18", fg="#9a978f")
    summary.pack(pady=(0, 8))

    frame = tk.Frame(root, bg="#1c1a18")
    frame.pack(fill="both", expand=True, padx=14)
    cols = ("swing", "progress", "done", "occluded", "left", "last")
    tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
    for c, txt, w, anchor in (
            ("swing", "Swing", 250, "w"), ("progress", "Progress", 110, "center"),
            ("done", "Annotated", 80, "center"), ("occluded", "Occluded", 80, "center"),
            ("left", "Left", 60, "center"), ("last", "Last edit", 140, "center")):
        tree.heading(c, text=txt)
        tree.column(c, width=w, anchor=anchor)
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="left", fill="y")
    tree.tag_configure("full", foreground="#7fd67f")
    tree.tag_configure("part", foreground="#e8d27f")

    def refresh():
        tree.delete(*tree.get_children())
        tot_done = tot_frames = full = 0
        for v in vids:
            done, occ, total, last = clip_stats(v)
            marked = done + occ
            tot_done += marked
            tot_frames += total
            pct = 100 * marked // total if total else 0
            if total and marked >= total:
                full += 1
                tag = ("full",)
            elif marked:
                tag = ("part",)
            else:
                tag = ()
            tree.insert("", "end", iid=v, tags=tag, values=(
                os.path.relpath(v, VID_DIR), f"{pct}%  ({marked}/{total})",
                done, occ, max(0, total - marked), last))
        summary.config(text=(
            f"{len(vids)} swings   |   {full} fully annotated   |   "
            f"{tot_done}/{tot_frames} frames done "
            f"({100 * tot_done // tot_frames if tot_frames else 0}%)"))
        if not vids:
            summary.config(text=f"No videos found - put clips in {VID_DIR}")
    refresh()

    chosen = []

    def on_open(_event=None):
        sel = tree.selection()
        if sel:
            chosen.append(sel[0])
            root.destroy()

    def on_export():
        out = export_session()
        if out:
            audit_append("-", -1, "export", {"zip": os.path.basename(out)})
            messagebox.showinfo("Export", f"Session exported:\n{out}")
        else:
            messagebox.showinfo("Export", "Nothing annotated today - nothing to export.")

    tree.bind("<Double-1>", on_open)
    tree.bind("<Return>", on_open)
    btns = tk.Frame(root, bg="#1c1a18")
    btns.pack(pady=10)
    tk.Button(btns, text="Annotate selected", command=on_open,
              font=("Helvetica", 12)).pack(side="left", padx=6)
    tk.Button(btns, text="Export session", command=on_export,
              font=("Helvetica", 12)).pack(side="left", padx=6)
    tk.Label(root, text="Double-click a swing to annotate it. Close this window to quit.",
             bg="#1c1a18", fg="#9a978f").pack(pady=(0, 10))
    root.mainloop()
    return chosen[0] if chosen else None


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        Annotator(pick_video()).run()
        return
    if len(sys.argv) > 1:
        Annotator(sys.argv[1]).run()
        return
    # GUI loop: picker -> annotate -> back to picker (with fresh stats)
    while True:
        vid = gui_pick_video()
        if vid is None:
            break
        Annotator(vid).run()


if __name__ == "__main__":
    print(__doc__)
    main()
