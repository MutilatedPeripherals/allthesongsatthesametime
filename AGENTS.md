# AGENTS.md

## Project overview

A Python tool that builds "guess the band" music challenges. Given a band or album name, it produces one single audio file that plays all of that band/album's songs at the same time. The repo has no commits yet.

## Structure

- `main.py` — entry point. Runnable directly: `python main.py -b <band> [-a <album>]`, with `--naive` for the browser-tabs approach. Album requires band.
  - `build_challenge(band_name, album_name)` — implemented: fetches song names, resolves each to a YouTube URL (yt-dlp search), downloads all as MP3 (best effort), then mixes them into one audio file via ffmpeg (`loudnorm` per track to -18 LUFS, then `amix` with sum/clip-limit — see `mix_mp3s`). Outputs to `./challenges/<scope>_challenge.mp3`.
  - `build_challenge_naive(band_name, album_name)` — naive approach, implemented: fetches song names from MusicBrainz, resolves each to a YouTube URL via yt-dlp search, then opens all of them as tabs in a single Playwright/Chromium window, accepts the cookie consent, and clicks play on each so they start near-simultaneously. Saves the URL list to `naive_<scope>.txt` and returns its path. Blocks until Enter is pressed, then closes the browser.
  - Helpers in `main.py`:
    - `fetch_song_names(band_name, album_name)` — MusicBrainz API (no key; User-Agent header required). Album → `release:"<album>" AND artist:"<band>"` search, then fetches candidate releases (limit 5) and picks the one with the fewest tracks (canonical edition, avoids bonus-track reissues). Band → browse `release` with `inc=recordings`, paginated via `offset`, deduped by track title. Retries on HTTP 503 and temporary connection errors.
    - `search_youtube_url(query)` — yt-dlp with `ytsearch1:` and `download=False`, with `remote_components: ["ejs:github"]` to fetch YouTube's JS challenge solver; returns first hit's URL or `None`.
    - `open_and_play(urls)` — Playwright sync-API chromium (headed). One browser context → all videos are tabs in one window. Each page: `_accept_cookies` (clicks "Accept all"/"Accept the lot"/"I agree"), then clicks `.ytp-large-play-button`, falling back to `.ytp-play-button` then the `k` shortcut.
- `utils.py` — `download_from_youtube_as_mp3(url: str) -> tuple[bool, Path | None]`.
  Downloads the best audio of a YouTube video as MP3 into `./downloads/` using `yt-dlp` + FFmpeg, renames the file to the video title, and caches URL→path in `download_cache.json`. Also uses `remote_components: ["ejs:github"]`.
  - `mix_mp3s(input_paths, output_path) -> bool` — mixes all MP3s (overlaid start at t=0) into one stereo MP3 via ffmpeg subprocess, per-track `loudnorm=I=-18:TP=-1.5:LRA=11` + `aformat stereo/48 kHz`, then `amix=inputs=N:duration=longest:normalize=0:dropout_transition=0` + `alimiter=limit=0.95`.
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