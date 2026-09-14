import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from yt_dlp import YoutubeDL

from utils import download_from_youtube_as_mp3, mix_mp3s

"""
This project is for supporting a "guess the band" challenge.
Given the band or album name, it builds one single audio file to use for the challenge, which is all the songs of that band/album at the same time
"""

MB_BASE = "https://musicbrainz.org/ws/2/"
MB_HEADERS = {"User-Agent": "allsongschallenge/0.1 (https://github.com/opencode/allsongschallenge)"}


def _mb_get(url: str) -> dict:
    req = urllib.request.Request(url, headers=MB_HEADERS)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code != 503 or attempt == 2:
                raise
        except urllib.error.URLError:
            if attempt == 2:
                raise
        time.sleep(2 * (attempt + 1))
    raise urllib.error.URLError("MusicBrainz request failed")


def fetch_song_names(band_name: str, album_name: str | None = None) -> list[str]:
    if album_name:
        query = urllib.parse.quote(f'release:"{album_name}" AND artist:"{band_name}"')
        try:
            releases = _mb_get(f"{MB_BASE}release/?query={query}&fmt=json&limit=5")["releases"]
        except urllib.error.URLError:
            return []
        if not releases:
            return []
        best_tracks: list[str] = []
        for release in releases:
            try:
                data = _mb_get(f"{MB_BASE}release/{release['id']}?inc=recordings&fmt=json")
            except urllib.error.URLError:
                continue
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
    try:
        data = _mb_get(f"{MB_BASE}artist/?query={query}&fmt=json&limit=1")
        artists = data.get("artists", [])
    except urllib.error.URLError:
        return []
    if not artists:
        return []

    songs: set[str] = set()
    try:
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
    except (urllib.error.URLError, urllib.error.HTTPError):
        pass
    return sorted(songs)


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


def build_challenge(band_name: str, album_name: str | None = None) -> Path:
    scope = album_name or band_name

    song_names = fetch_song_names(band_name, album_name)
    if not song_names:
        print(f"No songs found for {scope}.")
        return Path()

    downloaded: list[Path] = []
    for song in song_names:
        url = search_youtube_url(f"{song} {scope}")
        if not url:
            print(f"No YouTube video found for {song}.")
            continue
        print(f"Downloading {song}...")
        ok, path = download_from_youtube_as_mp3(url)
        if ok and path:
            downloaded.append(path)
        else:
            print(f"Failed to download {song}.")
    if not downloaded:
        print("No songs could be downloaded.")
        return Path()

    output_folder = Path.cwd().resolve() / "challenges"
    output_folder.mkdir(exist_ok=True)
    output = output_folder / f"{re.sub(r'[<>:\"/\\\\|?*]', ' ', scope)}_challenge.mp3"

    print(f"Mixing {len(downloaded)} songs into {output}...")
    if mix_mp3s(downloaded, output):
        return output
    return Path()


def build_challenge_naive(band_name: str, album_name: str | None = None) -> Path:
    scope = album_name or band_name

    song_names = fetch_song_names(band_name, album_name)
    if not song_names:
        print(f"No songs found for {scope}.")
        return Path()
    urls = []
    for song in song_names:
        url = search_youtube_url(f"{song} {scope}")
        if url:
            urls.append(url)

    if not urls:
        print(f"Could not find any YouTube videos for {scope}.")
        return Path()

    artifact = Path.cwd().resolve() / f"naive_{re.sub(r'[<>:\"/\\\\|?*]', ' ', scope)}.txt"
    artifact.write_text("\n".join(urls) + "\n")

    print(f"Opening {len(urls)} YouTube tabs for {scope}...")
    open_and_play(urls)
    return artifact


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build an all-songs challenge.")
    parser.add_argument("-b", "--band", required=True, help="Band name")
    parser.add_argument("-a", "--album", default=None, help="Album name (requires band)")
    parser.add_argument("--naive", action="store_true", help="Use the naive browser-tabs approach")
    args = parser.parse_args()

    if args.naive:
        challenge_file = build_challenge_naive(args.band, args.album)
    else:
        challenge_file = build_challenge(args.band, args.album)
    print(f"Challenge file: {challenge_file}")