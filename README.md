# shockz-mp3-manager-cli

A CLI for downloading YouTube audio and loading it onto **Shokz OpenSwim** (and similar) bone-conduction headphones in **MP3 mode**.

Shokz MP3 mode plays a **flat list at the drive root** — no folder browsing, only play/pause and forward/back. This tool is built around that constraint:

1. **Extract** YouTube URLs into a local library on your computer
2. **Manage an active pool** of tracks you want on the headset right now
3. **Sync** those MP3s to the device root (no subfolders)

Optional **voice intros** (macOS) speak the track name before the music starts — useful when you're biking, swimming, or running and can't see the filename.

## Why this exists

OpenSwim and related Shokz models are great for workouts, but getting music onto them is awkward: drag-and-drop works, yet skip/back through dozens of files is painful. This CLI keeps a large **archive** on your Mac while rotating a small **active pool** (~10 tracks) on the headset.

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| **Python 3.10+** | |
| **ffmpeg** | `brew install ffmpeg` (macOS) |
| **macOS** (optional) | Voice intros need the built-in `say` command |

## Install

```bash
git clone https://github.com/bcharleson/shockz-mp3-manager-cli.git
cd shockz-mp3-manager-cli

python3 -m venv venv
source venv/bin/activate
pip install -e .
```

Verify:

```bash
shockz --help
shockz config
```

## Configuration

All paths and defaults are controlled by **environment variables**. Copy the example file and edit:

```bash
cp .env.example .env
# edit .env, then:
set -a && source .env && set +a
```

| Variable | Default | Description |
|----------|---------|-------------|
| `SHOCKZ_LIBRARY_DIR` | `~/Music/shockz-library` | Local MP3 archive |
| `SHOCKZ_DEVICE_PATH` | `/Volumes/SWIM PRO` | Headset mount when USB-connected |
| `SHOCKZ_ANNOUNCE` | `true` | Enable voice intros on new downloads |
| `SHOCKZ_ANNOUNCE_VOICE` | `Samantha` | macOS TTS voice |
| `SHOCKZ_DEFAULT_BITRATE` | `320` | MP3 kbps for downloads |
| `SHOCKZ_RECOMMENDED_MAX_TRACKS` | `10` | Hint when active pool grows large |

Run `shockz config` to see effective settings.

**Audio files never live in this repo** — only the tool and your local `.env` (gitignored).

## Storage model

| Tier | Location | Purpose |
|------|----------|---------|
| **Library** | `SHOCKZ_LIBRARY_DIR` | Everything you've downloaded |
| **Active pool** | `.on-device.txt` in library dir | Tracks that should be on the headset |
| **Headset** | `SHOCKZ_DEVICE_PATH` (root only) | What's physically on the device |

## Quick start

```bash
# Plug in Shokz via USB (optional — auto-syncs if connected)
shockz extract "https://www.youtube.com/watch?v=VIDEO_ID"

# Eject when done (macOS)
diskutil eject '/Volumes/SWIM PRO'
```

With voice intros enabled, you'll hear a short spoken label, a brief pause, then the music.

## Voice intros

Voice intros use macOS `say` + ffmpeg. Disable globally:

```bash
export SHOCKZ_ANNOUNCE=false
```

Or per download:

```bash
shockz extract "https://youtube.com/..." --no-announce
```

Custom spoken line:

```bash
shockz extract "https://youtube.com/..." -a "my custom intro"
shockz announce "Track Name.mp3" -a "custom intro for existing file"
```

Re-running `announce` on the same file **prepends another intro** — run once per track unless redoing intentionally.

On Linux/Windows, use `--no-announce` or `SHOCKZ_ANNOUNCE=false` (no `say` available).

## Commands

### `extract` — download from YouTube

```bash
shockz extract "https://youtu.be/VIDEO_ID"
shockz extract "URL" -f "My Custom Title"
shockz extract "URL" --archive          # library only, not active pool
shockz extract "URL" --no-sync          # don't copy to headset
shockz extract "URL" -b 256
shockz extract "URL" --no-announce
```

| Flag | Short | Description |
|------|-------|-------------|
| `--bitrate` | `-b` | MP3 bitrate: 128, 192, 256, 320 |
| `--filename` | `-f` | Library filename (no extension) |
| `--announce` | `-a` | Custom spoken intro |
| `--no-announce` | | Skip voice intro |
| `--archive` | | Don't add to active pool |
| `--sync` / `--no-sync` | | Copy to headset after download |

### `pool` — manage the active pool

```bash
shockz pool list
shockz pool add "Track Name"
shockz pool remove "Old Track"
```

### `sync` — copy pool → headset

```bash
shockz sync                  # active pool only
shockz sync --prune          # remove headset files not in pool
shockz sync --all            # entire library (use sparingly)
shockz sync "partial name"   # one track
```

### `status`, `list`, `config`, `announce`

```bash
shockz status                # library vs pool vs device
shockz list                  # library filenames
shockz config                # show effective configuration
shockz announce "Track"      # add intro to existing file
```

## Typical workflows

**New track for the headset**

```bash
shockz extract "https://youtube.com/..."
diskutil eject '/Volumes/SWIM PRO'
```

**Stock up for later (don't put on headset)**

```bash
shockz extract "URL" --archive
```

**Rotate what's on the headset**

```bash
shockz pool remove "Old Mix"
shockz pool add "New Mix"
shockz sync --prune
```

## Shokz / OpenSwim notes

- OpenSwim mounts as **`SWIM PRO`** at `/Volumes/SWIM PRO` on macOS
- Use **MP3 mode** on the headset for local file playback
- Keep files at the **drive root** — nested folders may not be navigable
- Always eject before unplugging
- Copies use `copyfile` (not `copy2`) because the device uses FAT and rejects macOS metadata

## Stack

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — YouTube download
- [ffmpeg](https://ffmpeg.org/) — audio conversion and intro merging
- [Click](https://click.palletsprojects.com/) — CLI
- [Rich](https://github.com/Textualize/rich) — terminal output

## License

MIT — see [LICENSE](LICENSE).

## Contributing

Issues and PRs welcome. Please don't commit MP3s or personal `.env` files.
