## Setup

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```sh
# Download + mix all songs of an album into one MP3
python main.py -b "Death" -a "Leprosy"

# All songs of a band
python main.py -b "Wormrot"

# Options
python main.py -b "Death" -a "Leprosy" -o challenges   # output dir (created if missing)
python main.py -b "Death" -a "Leprosy" -y              # skip confirmation prompt
```

Album song lists come from Wikipedia (MusicBrainz as fallback); band lists from MusicBrainz. Output is `<output_dir>/<scope>_challenge.mp3`.

## Bonus: download a single YouTube video as MP3

We provide a notebook for this: `notebooks/download_from_youtube.ipynb` 

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/MutilatedPeripherals/allthesongsatthesametime/blob/main/notebooks/download_from_youtube.ipynb)

## Tests

```sh
python -m unittest discover -v
```