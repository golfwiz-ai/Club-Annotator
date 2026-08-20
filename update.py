#!/usr/bin/env python3
"""Self-updater for the swing annotator.

Run by the launchers before the app starts. Asks GitHub (anonymously, plain
HTTPS - no git or GitHub login needed) for the latest commit on main of
golfwiz-ai/Club-Annotator; if it differs from the locally recorded version,
downloads the zip snapshot and replaces the app files in place.

Only app files are touched - videos/, output/, annotations/ and venv/ are
never modified, so user data always survives an update. Offline or any
error = skip silently and start the app as-is.
"""

import io
import json
import os
import shutil
import urllib.request
import zipfile

REPO = "golfwiz-ai/Club-Annotator"
BRANCH = "main"
HERE = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(HERE, ".app_version")
# folders that hold user data / machine state: never replaced by an update
PRESERVE = {"videos", "output", "annotations", "venv", ".git",
            "__pycache__", ".app_version"}
TIMEOUT = 5   # seconds; a slow/absent network must not block startup


def _remote_sha():
    url = f"https://api.github.com/repos/{REPO}/commits/{BRANCH}"
    req = urllib.request.Request(url, headers={"User-Agent": "club-annotator"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)["sha"]


def _local_sha():
    try:
        with open(VERSION_FILE) as fh:
            return fh.read().strip()
    except OSError:
        return None


def update():
    try:
        remote = _remote_sha()
    except Exception:
        return   # offline, rate-limited, repo private/moved: just start the app
    if remote == _local_sha():
        return
    print("new version available - updating ...")
    try:
        url = f"https://codeload.github.com/{REPO}/zip/refs/heads/{BRANCH}"
        req = urllib.request.Request(url, headers={"User-Agent": "club-annotator"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            root = z.namelist()[0].split("/")[0]          # Club-Annotator-main/
            for info in z.infolist():
                rel = os.path.relpath(info.filename, root)
                if rel == "." or info.is_dir():
                    continue
                top = rel.split(os.sep)[0]
                if top in PRESERVE:
                    continue
                dst = os.path.join(HERE, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with z.open(info) as src, open(dst, "wb") as out:
                    shutil.copyfileobj(src, out)
                if rel.endswith((".sh", ".command")):
                    os.chmod(dst, 0o755)
        with open(VERSION_FILE, "w") as fh:
            fh.write(remote)
        print(f"updated to {remote[:12]}")
    except Exception as e:
        print(f"update failed ({e}) - starting the current version")


if __name__ == "__main__":
    update()
