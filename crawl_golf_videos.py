#!/usr/bin/env python3
"""Crawl YouTube for golf swing videos and build a metadata catalog.

Metadata only -- no video files are downloaded. Output is a JSON catalog
(and optional CSV) you can filter, then feed to a downloader later.

Requires:  pip install yt-dlp

Examples:
    python3 crawl_golf_videos.py
    python3 crawl_golf_videos.py --per-query 100 --max-duration 120
    python3 crawl_golf_videos.py -q "driver swing slow motion" -q "iron swing dtl"
    python3 crawl_golf_videos.py --channel https://www.youtube.com/@SomeGolfChannel/videos
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_QUERIES = [
    "golf swing slow motion",
    "golf swing face on",
    "golf swing down the line",
    "driver swing analysis",
    "iron swing slow motion",
    "pro golf swing 240fps",
    "amateur golf swing analysis",
    "golf swing front view",
]


def build_ydl_opts(quiet: bool) -> dict:
    return {
        "quiet": quiet,
        "no_warnings": quiet,
        "skip_download": True,
        "extract_flat": "in_playlist",  # search pages: entries without a full fetch
        "ignoreerrors": True,
        "noplaylist": False,
    }


def flatten_entries(info) -> list[dict]:
    """Walk yt-dlp's nested playlist/search result into a flat entry list."""
    if not info:
        return []
    # Flat extraction yields "url" stubs; a full fetch yields "video" (or no _type).
    if info.get("_type") in (None, "video", "url") and info.get("id"):
        return [info]
    out = []
    for entry in info.get("entries") or []:
        out.extend(flatten_entries(entry))
    return out


def normalize(entry: dict, source: str) -> dict | None:
    vid = entry.get("id")
    if not vid:
        return None
    return {
        "id": vid,
        "url": entry.get("url") or f"https://www.youtube.com/watch?v={vid}",
        "title": (entry.get("title") or "").strip(),
        "description": (entry.get("description") or "")[:2000],
        "duration_sec": entry.get("duration"),
        "channel": entry.get("channel") or entry.get("uploader"),
        "channel_url": entry.get("channel_url") or entry.get("uploader_url"),
        "view_count": entry.get("view_count"),
        "upload_date": entry.get("upload_date"),
        "thumbnail": entry.get("thumbnail"),
        "live_status": entry.get("live_status"),
        "found_via": source,
    }


def keep(rec: dict, args) -> bool:
    dur = rec.get("duration_sec")
    if dur is not None:
        if args.min_duration and dur < args.min_duration:
            return False
        if args.max_duration and dur > args.max_duration:
            return False
    elif args.require_duration:
        return False
    if rec.get("live_status") in ("is_live", "is_upcoming"):
        return False
    text = f"{rec['title']} {rec.get('description', '')}".lower()
    if args.exclude and any(t.lower() in text for t in args.exclude):
        return False
    if args.require and not any(t.lower() in text for t in args.require):
        return False
    return True


def crawl(args) -> list[dict]:
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        sys.exit("yt-dlp is not installed.  Run:  pip install yt-dlp")

    targets: list[tuple[str, str]] = []  # (yt-dlp target, human source label)
    for q in args.query or DEFAULT_QUERIES:
        targets.append((f"ytsearch{args.per_query}:{q}", f"search:{q}"))
    for url in args.channel or []:
        targets.append((url, f"channel:{url}"))

    seen: dict[str, dict] = {}
    with YoutubeDL(build_ydl_opts(not args.verbose)) as ydl:
        for target, label in targets:
            print(f"[crawl] {label}", file=sys.stderr)
            try:
                info = ydl.extract_info(target, download=False)
            except Exception as exc:  # noqa: BLE001 - one bad query shouldn't kill the run
                print(f"[warn]  {label}: {exc}", file=sys.stderr)
                continue
            kept = 0
            for entry in flatten_entries(info):
                rec = normalize(entry, label)
                if not rec or rec["id"] in seen:
                    continue
                if not keep(rec, args):
                    continue
                seen[rec["id"]] = rec
                kept += 1
            print(f"[crawl] {label}: +{kept} (total {len(seen)})", file=sys.stderr)

    return list(seen.values())


def write_outputs(records: list[dict], args) -> None:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(records),
        "filters": {
            "min_duration": args.min_duration,
            "max_duration": args.max_duration,
            "require": args.require,
            "exclude": args.exclude,
        },
        "videos": records,
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"[done]  {len(records)} videos -> {out}", file=sys.stderr)

    if args.csv:
        cols = ["id", "url", "title", "channel", "duration_sec", "view_count",
                "upload_date", "found_via"]
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(records)
        print(f"[done]  csv -> {args.csv}", file=sys.stderr)

    if args.urls:
        Path(args.urls).write_text("\n".join(r["url"] for r in records) + "\n")
        print(f"[done]  urls -> {args.urls}", file=sys.stderr)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-q", "--query", action="append",
                   help="search query (repeatable; defaults to a built-in golf set)")
    p.add_argument("-c", "--channel", action="append",
                   help="channel/playlist URL to enumerate (repeatable)")
    p.add_argument("-n", "--per-query", type=int, default=50,
                   help="results per search query (default 50)")
    p.add_argument("--min-duration", type=int, default=0,
                   help="drop videos shorter than N seconds")
    p.add_argument("--max-duration", type=int, default=0,
                   help="drop videos longer than N seconds (0 = no limit)")
    p.add_argument("--require-duration", action="store_true",
                   help="drop entries with unknown duration")
    p.add_argument("--require", action="append",
                   help="keep only titles/descriptions containing one of these terms")
    p.add_argument("--exclude", action="append",
                   default=["podcast", "vlog", "highlights", "full round"],
                   help="drop titles/descriptions containing these terms")
    p.add_argument("-o", "--out", default="catalog/golf_videos.json",
                   help="JSON catalog path")
    p.add_argument("--csv", help="also write a flat CSV here")
    p.add_argument("--urls", help="also write a plain URL list here")
    p.add_argument("-v", "--verbose", action="store_true", help="verbose yt-dlp output")
    args = p.parse_args()

    records = crawl(args)
    records.sort(key=lambda r: (r.get("view_count") or 0), reverse=True)
    write_outputs(records, args)


if __name__ == "__main__":
    main()
