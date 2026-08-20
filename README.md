# Club-Annotator

Standalone two-click golf-club annotator. Put clips in `videos/` (subfolders
fine), double-click the launcher for your OS, and annotate: 1st click = club
head, 2nd click = grip, auto-advance. Output lands in `output/<date>/` as
`<date>_<serial>` video copy + CSV pairs.

- macOS: `Start Annotator.command`
- Windows: `Start Annotator (Windows).bat`
- Linux: `run.sh`

The launcher auto-installs its Python environment on first run and
auto-updates the app from this repo's `main` branch on every start
(anonymously — no GitHub login or git needed on the user's machine).

See `README.txt` for full user instructions and the key map.
