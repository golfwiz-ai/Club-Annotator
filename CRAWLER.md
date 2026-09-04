# Golf video crawler

Builds a **metadata-only** catalog of golf swing videos from YouTube search and
channel/playlist pages. No video files are downloaded — the output is a list you
can filter first and fetch later.

## Install

```sh
pip install yt-dlp          # or: python3 -m venv .venv && .venv/bin/pip install yt-dlp
```

## Use

```sh
# default golf swing query set, 50 results each
python3 crawl_golf_videos.py

# short clips only, custom queries, all three output formats
python3 crawl_golf_videos.py \
  -q "golf swing slow motion" -q "iron swing down the line" \
  -n 100 --min-duration 5 --max-duration 120 \
  -o catalog/golf_videos.json --csv catalog/golf_videos.csv --urls catalog/urls.txt

# enumerate a whole channel
python3 crawl_golf_videos.py --channel https://www.youtube.com/@SomeGolfChannel/videos
```

## Options

| Flag | Meaning |
| --- | --- |
| `-q/--query` | Search query, repeatable. Defaults to a built-in golf swing set. |
| `-c/--channel` | Channel or playlist URL to enumerate, repeatable. |
| `-n/--per-query` | Results per query (default 50). |
| `--min-duration` / `--max-duration` | Duration filter in seconds. |
| `--require-duration` | Drop entries whose duration is unknown. |
| `--require` | Keep only titles/descriptions matching one of these terms. |
| `--exclude` | Drop matches. Defaults to podcast / vlog / highlights / full round. |
| `-o`, `--csv`, `--urls` | JSON catalog, flat CSV, plain URL list. |

Results are deduped by video ID across all queries and sorted by view count.
Live and upcoming streams are always skipped.

## Fetching later

The `--urls` file feeds straight into yt-dlp:

```sh
yt-dlp -a catalog/urls.txt -o 'videos/%(id)s.%(ext)s'
```

Respect YouTube's terms of service and each creator's rights when downloading.
