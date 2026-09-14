# AGENTS.md

## Project overview

A Python tool that builds "guess the band" music challenges. Given a band or album name, it produces one single audio file that plays all of that band/album's songs at the same time. The repo has no commits yet.

## Structure

- `main.py` — entry point. Runnable directly: `python main.py <band>` or `python main.py <band> --album <album>` (album optional; if given, band is required).
  - `build_challenge(band_name: str, album_name: str | None = None) -> Path` — planned approach: fetch song names, download each from YouTube as MP3, then mix them into one output audio file (keep stereo, normalize volumes). Currently a stub returning an empty `Path()`.
  - `build_challenge_naive(band_name: str, album_name: str | None = None) -> Path` — naive approach, implemented: fetches song names from MusicBrainz, resolves each to a YouTube URL via yt-dlp search, then opens all of them as browser tabs (Playwright/Chromium) and clicks play on each so they start near-simultaneously. Saves the URL list to `naive_<scope>.txt` and returns its path. Blocks until Enter is pressed, then closes the browser.
  - Helpers in `main.py`:
    - `fetch_song_names(band_name, album_name)` — MusicBrainz API (no key; User-Agent header required). Album → release lookup with `inc=recordings` (always `release:... AND artist:...`, since album requires band). Band → browse `release` with `inc=recordings`, paginated via `offset`, deduped by track title. Retries on HTTP 503.
    - `search_youtube_url(query)` — yt-dlp with `ytsearch1:` and `download=False`; returns first hit's URL or `None`.
    - `open_and_play(urls)` — Playwright sync-API chromium (headed), one tab per URL, clicks `.ytp-large-play-button` (falls back to the `k` shortcut).
- `utils.py` — `download_from_youtube_as_mp3(url: str) -> tuple[bool, Path | None]`.
  Downloads the best audio of a YouTube video as MP3 into `./downloads/` using `yt-dlp` + FFmpeg, renames the file to the video title, and caches URL→path in `download_cache.json`.
- `requirements.txt` — `yt-dlp` and `playwright`.

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