import json
import re
import subprocess
import threading
import uuid
from pathlib import Path

from yt_dlp import YoutubeDL

_CACHE_LOCK = threading.Lock()

def download_from_youtube_as_mp3(url: str) -> tuple[bool, Path | None]:
    if not re.match(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/", url):
        raise ValueError("The provided URL is not a valid YouTube video URL.")

    cache_file = Path.cwd().resolve() / "download_cache.json"
    if cache_file.exists():
        with open(cache_file, "r") as f:
            cache = json.load(f)
        if url in cache:
            cached_path = Path(cache[url])
            if cached_path.exists():
                print("Using cached download.")
                return True, cached_path
    else:
        cache = {}

    output_folder = Path.cwd().resolve() / "downloads"
    output_folder.mkdir(exist_ok=True)

    temp_name = str(uuid.uuid4())
    temp_path = str(output_folder / f"{temp_name}.%(ext)s")

    opts = {
        "format": "bestaudio/best",
        "extractaudio": True,
        "audioformat": "mp3",
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
        "outtmpl": temp_path,
        "noplaylist": True,
        "quiet": False,
        "remote_components": ["ejs:github"],
    }

    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

            if info is None:
                print("Failed to download video.")
                return False, None

            title = re.sub(r'[<>:"/\\|?*]', " ", info.get("title", temp_name))
            final_path = output_folder / f"{title}.mp3"
            downloaded_path = output_folder / f"{temp_name}.mp3"

            if downloaded_path.exists():
                downloaded_path.rename(final_path)

            with _CACHE_LOCK:
                cache = {}
                if cache_file.exists():
                    try:
                        cache = json.loads(cache_file.read_text())
                    except (json.JSONDecodeError, OSError):
                        cache = {}
                cache[url] = str(final_path)
                cache_file.write_text(json.dumps(cache, indent=2))

            return True, final_path

    except Exception as e:
        print(f"Error: {e}")
        return False, None


def mix_mp3s(input_paths: list[Path], output_path: Path) -> bool:
    if not input_paths:
        return False

    inputs = []
    filters = []
    for i, path in enumerate(input_paths):
        inputs += ["-i", str(path)]
        filters.append(
            f"[{i}:a]loudnorm=I=-18:TP=-1.5:LRA=11,"
            f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a{i}]"
        )
    mix_in = "".join(f"[a{i}]" for i in range(len(input_paths)))
    filters.append(
        f"{mix_in}amix=inputs={len(input_paths)}:duration=longest:normalize=0:dropout_transition=0,"
        f"alimiter=limit=0.95[out]"
    )

    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[out]",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "2",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        print("ffmpeg not found; cannot mix audio.")
        return False

    if result.returncode != 0:
        print(f"Failed to mix audio: {result.stderr[-2000:]}")
        return False
    return output_path.exists()
