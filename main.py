import html.parser
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from yt_dlp import YoutubeDL

from utils import download_from_youtube_as_mp3, mix_mp3s

"""
This project is for supporting a "guess the band" challenge.
Given the band or album name, it builds one single audio file to use for the challenge, which is all the songs of that band/album at the same time
"""

MB_BASE = "https://musicbrainz.org/ws/2/"
MB_HEADERS = {"User-Agent": "allsongschallenge/0.1 (https://github.com/opencode/allsongschallenge)"}
WIKI_BASE = "https://en.wikipedia.org/wiki/"
WIKI_HEADERS = {"User-Agent": "allsongschallenge/0.1 (https://github.com/opencode/allsongschallenge)"}
DOWNLOAD_CONCURRENCY = 3


def format_elapsed(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60:02d}s"
    return f"{seconds // 3600}h {(seconds % 3600) // 60:02d}m"


_LAST_MB_CALL = 0.0


def _mb_get(url: str) -> dict:
    global _LAST_MB_CALL
    req = urllib.request.Request(url, headers=MB_HEADERS)
    for attempt in range(3):
        wait = 1.1 - (time.monotonic() - _LAST_MB_CALL)
        if wait > 0:
            time.sleep(wait)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                _LAST_MB_CALL = time.monotonic()
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if attempt == 2 or e.code != 503:
                raise
        except urllib.error.URLError:
            if attempt == 2:
                raise
        time.sleep(2 + 2 * attempt)
    raise urllib.error.URLError("MusicBrainz request failed")


def fetch_song_names(band_name: str, album_name: str | None = None) -> list[str]:
    if album_name:
        songs = fetch_song_names_wikipedia(band_name, album_name)
        if songs:
            return songs
        print(f"Wikipedia found no songs for {album_name}, falling back to MusicBrainz...")
    try:
        return _fetch_song_names(band_name, album_name)
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"MusicBrainz API error: {e}")
        return []


def _fetch_song_names(band_name: str, album_name: str | None = None) -> list[str]:
    if album_name:
        query = urllib.parse.quote(f'release:"{album_name}" AND artist:"{band_name}"')
        releases = _mb_get(f"{MB_BASE}release/?query={query}&fmt=json&limit=5")["releases"]
        if not releases:
            return []
        best_tracks: list[str] = []
        for release in releases:
            data = _mb_get(f"{MB_BASE}release/{release['id']}?inc=recordings&fmt=json")
            tracks = [
                track["title"]
                for medium in data.get("media", [])
                for track in medium.get("tracks", [])
                if "title" in track
            ]
            if not best_tracks or len(tracks) < len(best_tracks):
                best_tracks = tracks
        return best_tracks

    query = urllib.parse.quote(f"artist:{band_name}")
    data = _mb_get(f"{MB_BASE}artist/?query={query}&fmt=json&limit=1")
    artists = data.get("artists", [])
    if not artists:
        return []

    songs: set[str] = set()
    for offset in range(0, 500, 100):
        batch = _mb_get(
            f"{MB_BASE}release?artist={artists[0]['id']}&inc=recordings&limit=100&offset={offset}&fmt=json"
        )
        releases = batch.get("releases", [])
        songs.update(
            track["title"]
            for release in releases
            for medium in release.get("media", [])
            for track in medium.get("tracks", [])
            if track.get("title")
        )
        if len(releases) < 100:
            break
    return sorted(songs)


class _TracklistParser(html.parser.HTMLParser):
    TITLE_COLUMNS = {"title", "song", "track", "name", "track title"}
    MISSABLE_WORDS = {
        "title", "song", "track", "name", "no.", "length", "time",
        "duration", "writer", "producer", "total length",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[tuple[list[str], list[list[str]]]] = []
        self._in_tracklist = 0
        self._header: list[str] | None = None
        self._rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._row_is_header = False

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class", "")
        if tag == "table":
            if "tracklist" in cls.split():
                self._in_tracklist = 1
                self._header = None
                self._rows = []
            elif self._in_tracklist:
                self._in_tracklist += 1
            return
        if not self._in_tracklist:
            return
        if tag == "tr":
            self._row_is_header = self._header is None
            self._row = []
        elif tag in ("th", "td") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if not self._in_tracklist:
            return
        if tag in ("th", "td") and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row_is_header:
                self._header = self._row
            else:
                self._rows.append(self._row)
            self._row = None
        elif tag == "table" and self._in_tracklist:
            self._in_tracklist -= 1
            if self._in_tracklist == 0 and self._header is not None:
                self.tables.append((self._header, self._rows))

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _parse_wikipedia_tracklist(page_html: str) -> list[str]:
    parser = _TracklistParser()
    parser.feed(page_html)
    for header, rows in parser.tables:
        title_idx = next(
            (i for i, cell in enumerate(header) if cell.strip().lower() in _TracklistParser.TITLE_COLUMNS),
            None,
        )
        if title_idx is None:
            continue
        tracks: list[str] = []
        for cells in rows:
            if len(cells) <= title_idx:
                continue
            title = cells[title_idx].strip().strip('"').strip()
            title = re.sub(r"\s*\[\w+\]$", "", title)
            if (
                title
                and title.lower() not in _TracklistParser.MISSABLE_WORDS
                and not title.isdigit()
                and not re.fullmatch(r"\d{1,3}:\d{2}", title)
            ):
                if title not in tracks:
                    tracks.append(title)
        if tracks:
            return tracks
    return []


def fetch_song_names_wikipedia(band_name: str, album_name: str) -> list[str]:
    candidates = (
        f"{album_name} ({band_name} album)",
        f"{album_name} ({band_name} Album)",
        album_name,
    )
    for title in candidates:
        url = WIKI_BASE + urllib.parse.quote(title.replace(" ", "_"))
        try:
            req = urllib.request.Request(url, headers=WIKI_HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                page = resp.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as e:
            print(f"Wikipedia fetch failed for {title!r}: {e}")
            continue
        tracks = _parse_wikipedia_tracklist(page)
        if tracks:
            return tracks
        print(f"No tracklist found on Wikipedia page {title!r}.")
    print(f"No Wikipedia page found for {album_name} by {band_name}.")
    return []


def search_youtube_url(query: str) -> str | None:
    try:
        with YoutubeDL({"quiet": True, "noplaylist": True, "remote_components": ["ejs:github"]}) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            entries = (info or {}).get("entries") or []
            if entries:
                return entries[0].get("webpage_url")
    except Exception:
        return None
    return None


def _accept_cookies(page) -> None:
    consent = page.locator(
        'button:has-text("Accept all"), button:has-text("Accept the lot"), button:has-text("I agree")'
    ).first
    try:
        consent.click(timeout=5_000)
    except Exception:
        pass


def open_and_play(urls: list[str]) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        try:
            context = browser.new_context()
            pages = []
            for url in urls:
                try:
                    page = context.new_page()
                    page.goto(url, timeout=120_000, wait_until="domcontentloaded")
                    pages.append(page)
                except Exception as e:
                    print(f"Failed to open {url}: {e}")
            for page in pages:
                try:
                    _accept_cookies(page)
                    page.wait_for_selector(".ytp-large-play-button", timeout=15_000)
                    page.click(".ytp-large-play-button")
                except Exception:
                    try:
                        page.click(".ytp-play-button", timeout=5_000)
                    except Exception:
                        page.keyboard.press("k")
            input("Press Enter to close the browser and stop playback...")
        finally:
            browser.close()


def _confirm_songs(song_names: list[str], scope: str) -> bool:
    print(f"\nFound {len(song_names)} songs for {scope}:")
    for index, song in enumerate(song_names, 1):
        print(f"  {index:>3}. {song}")
    answer = input("\nDownload all of these? [y/N] ").strip().lower()
    return answer in ("y", "yes")


def _download_song(song: str, band_name: str) -> Path | None:
    url = search_youtube_url(f"{song} {band_name}")
    if not url:
        print(f"No YouTube video found for {song}.")
        return None
    print(f"Downloading {song}...")
    ok, path = download_from_youtube_as_mp3(url)
    if ok and path:
        return path
    print(f"Failed to download {song}.")
    return None


def build_challenge(
    band_name: str, album_name: str | None = None, confirm: bool = True, output_dir: str = "challenges"
) -> Path:
    t0 = time.perf_counter()
    scope = album_name or band_name

    song_names = fetch_song_names(band_name, album_name)
    if not song_names:
        print(f"No songs found for {scope}.")
        return Path()
    print(f"Fetched {len(song_names)} songs in {format_elapsed(time.perf_counter() - t0)}.")

    if confirm and not _confirm_songs(song_names, scope):
        print("Aborted.")
        return Path()

    t1 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=DOWNLOAD_CONCURRENCY) as executor:
        downloaded = [
            path
            for path in executor.map(lambda song: _download_song(song, band_name), song_names)
            if path is not None
        ]
    if not downloaded:
        print("No songs could be downloaded.")
        return Path()
    print(f"Downloaded {len(downloaded)} songs in {format_elapsed(time.perf_counter() - t1)}.")

    output_folder = Path(output_dir).resolve()
    output_folder.mkdir(parents=True, exist_ok=True)
    output = output_folder / f"{re.sub(r'[<>:\"/\\\\|?*]', ' ', scope)}_challenge.mp3"

    print(f"Mixing {len(downloaded)} songs into {output}...")
    if mix_mp3s(downloaded, output):
        print(f"Challenge ready in {format_elapsed(time.perf_counter() - t0)} total.")
        return output
    return Path()


def build_challenge_naive(
    band_name: str, album_name: str | None = None, output_dir: str = "challenges"
) -> Path:
    scope = album_name or band_name

    song_names = fetch_song_names(band_name, album_name)
    if not song_names:
        print(f"No songs found for {scope}.")
        return Path()
    urls = []
    for song in song_names:
        url = search_youtube_url(f"{song} {band_name}")
        if url:
            urls.append(url)

    if not urls:
        print(f"Could not find any YouTube videos for {scope}.")
        return Path()

    artifact_folder = Path(output_dir).resolve()
    artifact_folder.mkdir(parents=True, exist_ok=True)
    artifact = artifact_folder / f"naive_{re.sub(r'[<>:\"/\\\\|?*]', ' ', scope)}.txt"
    artifact.write_text("\n".join(urls) + "\n")

    print(f"Opening {len(urls)} YouTube tabs for {scope}...")
    open_and_play(urls)
    return artifact


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build an all-songs challenge.")
    parser.add_argument("-b", "--band", required=True, help="Band name")
    parser.add_argument("-a", "--album", default=None, help="Album name (requires band)")
    parser.add_argument("-o", "--output", default="challenges", help="Output directory (created if missing)")
    parser.add_argument("--naive", action="store_true", help="Use the naive browser-tabs approach")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip the song-list confirmation")
    args = parser.parse_args()

    start = time.perf_counter()
    if args.naive:
        challenge_file = build_challenge_naive(args.band, args.album, output_dir=args.output)
    else:
        challenge_file = build_challenge(
            args.band, args.album, confirm=not args.yes, output_dir=args.output
        )
    print(f"Challenge file: {challenge_file}")
    print(f"Total time: {format_elapsed(time.perf_counter() - start)}")