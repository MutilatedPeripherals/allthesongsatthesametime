from pathlib import Path

from utils import download_from_youtube_as_mp3

"""
This project is for supporting a "guess the band" challenge. 
Given the band or album name, it builds one single audio file to use for the challenge, which is all the songs of that band/album at the same time
"""
def build_challenge(band_name: str, album_name: str|None=None) -> Path:
    # fetch all the song names of the band (if album is provided, use that instead)

    # download all the songs from youtube (best effort, if something fails, let it fail graciously

    # mix all the downloaded songs into one output audio file, ideally keep stereo and volumes normalized

    audio_path = Path()
    return audio_path

def build_challenge_naive(band_name: str, album_name: str|None=None) -> Path:
    # this one can be done with puppeteer.

    # fetch all the song names of the band (if album is provided, use that instead)

    # open all the songs as youtube tabs and play them all at the same time

    audio_path = Path()
    return audio_path

