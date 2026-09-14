## Setup

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Usage

```sh
# Download + mix all songs of an album into one MP3
python main.py -b "Death" -a "Leprosy"

# All songs of a band
python main.py -b "Wormrot"

# Naive approach: open all songs as simultaneous YouTube browser tabs
python main.py -b "Wormrot" -a "Dirge" --naive

# Options
python main.py -b "Death" -a "Leprosy" -o challenges   # output dir (created if missing)
python main.py -b "Death" -a "Leprosy" -y              # skip confirmation prompt
```

Album song lists come from Wikipedia (MusicBrainz as fallback); band lists from MusicBrainz. Output is `<output_dir>/<scope>_challenge.mp3`.

## Tests

```sh
python -m unittest discover -v
```