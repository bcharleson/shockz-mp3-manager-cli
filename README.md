# Shokz MP3 Manager

A small CLI for downloading YouTube audio and loading it onto **Shokz OpenSwim** bone-conduction headphones in MP3 mode.

Built for a simple two-step workflow: **extract to a local library**, then **sync flat to the headset**. Shokz MP3 mode plays a root-level track list — it does not browse folders — so this tool keeps the drive layout minimal on purpose.

## Why this exists

- Download any public YouTube video as a high-quality MP3
- Keep a permanent library on your Mac at `~/Documents/mp3-songs`
- Copy tracks to the headset root when `SWIM PRO` is plugged in via USB
- Avoid managing subfolders on the device

## Prerequisites

- **Python 3.10+**
- **ffmpeg** — `brew install ffmpeg`
- **yt-dlp** dependencies — installed via `requirements.txt`

## Setup

```bash
git clone git@github.com:bcharleson/mp3-yt-extractor.git
cd mp3-yt-extractor

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Where files live

| Location | Purpose |
|----------|---------|
| `~/Documents/mp3-songs/` | Local MP3 library (source of truth) |
| `/Volumes/SWIM PRO/` | Shokz headset — flat root only |

Audio files stay outside this repo. The tool manages paths; it does not store your music in git.

## Quick start

```bash
source venv/bin/activate

# 1. Plug in Shokz (optional — auto-syncs if connected)
# 2. Download a track
python extractor.py extract "https://www.youtube.com/watch?v=VIDEO_ID"

# 3. Eject when done
diskutil eject '/Volumes/SWIM PRO'
```

## Commands

### `extract` — download from YouTube

Saves to `~/Documents/mp3-songs/`. Syncs to the headset automatically when `SWIM PRO` is mounted, unless you pass `--no-sync`.

```bash
python extractor.py extract "https://youtu.be/VIDEO_ID"
python extractor.py extract "https://youtu.be/VIDEO_ID" -f "My Custom Title"
python extractor.py extract "https://youtu.be/VIDEO_ID" --no-sync
python extractor.py extract "https://youtu.be/VIDEO_ID" -b 256
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--bitrate` | `-b` | `320` | MP3 bitrate: `128`, `192`, `256`, `320` |
| `--filename` | `-f` | video title | Library filename without `.mp3` |
| `--sync` / `--no-sync` | | sync if connected | Copy to headset after download |

### `sync` — copy library → headset

Writes MP3s to the **root** of `SWIM PRO`. No subfolders.

```bash
# Sync entire library
python extractor.py sync

# Sync one track (exact name or partial match)
python extractor.py sync "Vol. 27"
python extractor.py sync "Two Friends - Big Bootie Mix, Vol. 27.mp3"
```

### `list` — show library contents

```bash
python extractor.py list
```

## Typical workflows

**New track while headset is plugged in**

```bash
python extractor.py extract "https://youtube.com/..."
diskutil eject '/Volumes/SWIM PRO'
```

**Batch refresh after adding several tracks offline**

```bash
python extractor.py extract "..." --no-sync
python extractor.py extract "..." --no-sync
# plug in headset
python extractor.py sync
```

**Check what you have before a swim**

```bash
python extractor.py list
```

## Shokz notes

- The OpenSwim mounts as **`SWIM PRO`** at `/Volumes/SWIM PRO`
- Use **MP3 mode** on the headset for local file playback
- Keep files at the drive root — nested folders may not be navigable in MP3 mode
- Always eject before unplugging: `diskutil eject '/Volumes/SWIM PRO'`

## Stack

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — YouTube download
- [ffmpeg](https://ffmpeg.org/) — audio conversion
- [Click](https://click.palletsprojects.com/) — CLI
- [Rich](https://github.com/Textualize/rich) — terminal output

## License

Private personal tool. Not licensed for redistribution.
