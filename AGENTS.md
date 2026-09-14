# AGENTS.md

## Project overview

A Python tool that builds "guess the band" music challenges. Given a band or album name, it produces one single audio file that plays all of that band/album's songs at the same time. The repo has no commits yet.

## Structure

- `main.py` — entry point.
  - `build_challenge(band_name: str, album_name: str | None = None) -> Path` — planned approach: fetch song names, download each from YouTube as MP3, then mix them into one output audio file (keep stereo, normalize volumes). Currently a stub returning an empty `Path()`.
  - `build_challenge_naive(band_name: str, album_name: str | None = None) -> Path` — naive approach: open all songs as YouTube tabs and play them simultaneously (e.g. via puppeteer). Currently a stub returning an empty `Path()`.
- `utils.py` — `download_from_youtube_as_mp3(url: str) -> tuple[bool, Path | None]`.
  Downloads the best audio of a YouTube video as MP3 into `./downloads/` using `yt-dlp` + FFmpeg, renames the file to the video title, and caches URL→path in `download_cache.json`.
- `requirements.txt` — only dependency is `yt-dlp`.

## Environment

- Python 3.13, virtualenv at `.venv/` (activate before running).
- Uses a PyCharm project (`.idea/`). `.gitignore` covers `.venv/` and `.idea/`.
- Runtime artifacts to keep out of git (recommended `.gitignore` entries):
  - `.venv/`
  - `.idea/`
  - `downloads/`
  - `download_cache.json`
  - `__pycache__/`

## Key behaviors to preserve

- `download_from_youtube_as_mp3` raises `ValueError` for non-YouTube URLs.
- Invalidates cached entries whose file no longer exists (re-downloads).
- Returns `(False, None)` on download failure instead of raising.
- Challenge building should be best-effort: if a song download fails, fail graciously rather than aborting.