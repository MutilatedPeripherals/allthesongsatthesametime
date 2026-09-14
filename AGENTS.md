# AGENTS.md

## Project overview

A Python tool that builds "guess the band" music challenges. Given a band or album name, it produces one single audio file that plays all of that band/album's songs at the same time. The repo has no commits yet.

## Structure

- `main.py` — entry point. Runnable directly: `python main.py -b <band> [-a <album>]`, with `--naive` for the browser-tabs approach. Album requires band.
  - `build_challenge(band_name, album_name, confirm=True)` — implemented: fetches song names, shows the list and asks for confirmation before downloading (`-y` in the CLI skips the prompt), resolves each to a YouTube URL (yt-dlp search with `"<song> <band>"` query), downloads all as MP3 (best effort, 3 at a time via `ThreadPoolExecutor` — see `DOWNLOAD_CONCURRENCY`), then mixes them into one audio file via ffmpeg (`loudnorm` per track to -18 LUFS, then `amix` with sum/clip-limit — see `mix_mp3s`). Outputs to `./challenges/<scope>_challenge.mp3`.
  - `build_challenge_naive(band_name, album_name)` — naive approach, implemented: fetches song names from MusicBrainz, resolves each to a YouTube URL via yt-dlp search (band-name query), then opens all of them as tabs in a single Playwright/Chromium window, accepts the cookie consent, and clicks play on each so they start near-simultaneously. Saves the URL list to `naive_<scope>.txt` and returns its path. Blocks until Enter is pressed, then closes the browser.
  - Helpers in `main.py`:
    - `fetch_song_names(band_name, album_name)` — Wikipedia first when an album is given (`fetch_song_names_wikipedia`); if that finds nothing, falls back to MusicBrainz (`_fetch_song_names`). Band-only requests go straight to MusicBrainz.
    - `_fetch_song_names(...)` — MusicBrainz API (no key; User-Agent header required). Album → `release:"<album>" AND artist:"<band>"` search, then fetches candidate releases (limit 5) and picks the one with the fewest tracks (canonical edition, avoids bonus-track reissues). Band → browse `release` with `inc=recordings`, paginated via `offset`, deduped by track title. Retries on HTTP 503 and temporary connection errors; paced to ≥1 request/sec (MusicBrainz etiquette).
    - `fetch_song_names_wikipedia(band_name, album_name)` — primary source for albums: fetches `https://en.wikipedia.org/wiki/<Album> (<Band> album)` (plain album title as second try) via urllib, parses the first `<table class="tracklist">` with `html.parser`, reads the "Title" column (handles `th scope="row"` numbering, quotes, footnote brackets, `Total length`/time rows). Returns the canonical first-list track titles.
    - `search_youtube_url(query)` — yt-dlp with `ytsearch1:` and `download=False`, with `remote_components: ["ejs:github"]` to fetch YouTube's JS challenge solver; returns first hit's URL or `None`.
    - `open_and_play(urls)` — Playwright sync-API chromium (headed). One browser context → all videos are tabs in one window. Each page: `_accept_cookies` (clicks "Accept all"/"Accept the lot"/"I agree"), then clicks `.ytp-large-play-button`, falling back to `.ytp-play-button` then the `k` shortcut.
- `utils.py` — `download_from_youtube_as_mp3(url: str) -> tuple[bool, Path | None]`.
  Downloads the best audio of a YouTube video as MP3 into `./downloads/` using `yt-dlp` + FFmpeg, renames the file to the video title, and caches URL→path in `download_cache.json` (thread-safe: re-reads + merges under a lock before writing). Also uses `remote_components: ["ejs:github"]`.
  - `mix_mp3s(input_paths, output_path) -> bool` — mixes all MP3s (overlaid start at t=0) into one stereo MP3 via ffmpeg subprocess, per-track `loudnorm=I=-18:TP=-1.5:LRA=11` + `aformat stereo/48 kHz`, then `amix=inputs=N:duration=longest:normalize=0:dropout_transition=0` + `alimiter=limit=0.95`.
- `requirements.txt` — `yt-dlp` and `playwright`.
- `tests/test_main.py` — `unittest` (stdlib, no pytest). Mocks MusicBrainz API (`_mb_get`) and YouTube search/download/mix so no network calls happen. Run with `.venv/bin/python -m unittest discover -v`. Covers `build_challenge` (success, failed download, missing URL, no songs, aborted confirm), `fetch_song_names` (fewest-track album, dedupe, unknown artist, Wikipedia fallback on error/empty), `_parse_wikipedia_tracklist`, `_confirm_songs`, and `format_elapsed`.

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