"""YouTube extraction and voice intro merging."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import yt_dlp

from shockz.config import Settings


def build_ydl_options(output_dir: Path, bitrate: str, filename: str | None) -> dict:
    output_template = str(output_dir / (filename if filename else "%(title)s")) + ".%(ext)s"
    return {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": bitrate,
            },
            {"key": "FFmpegMetadata", "add_metadata": True},
            {"key": "EmbedThumbnail"},
        ],
        "writethumbnail": True,
        "quiet": True,
        "no_warnings": False,
    }


def extract_url(url: str, output_dir: Path, bitrate: str, filename: str | None) -> dict:
    options = build_ydl_options(output_dir, bitrate, filename)
    with yt_dlp.YoutubeDL(options) as ydl:
        return ydl.extract_info(url, download=True)


def output_path(info: dict, output_dir: Path, filename: str | None) -> Path:
    if filename:
        return output_dir / f"{filename}.mp3"
    title = info.get("title", "download")
    return output_dir / f"{title}.mp3"


def run_command(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(detail or f"Command failed: {' '.join(command)}") from exc


def prepend_voice_announcement(
    mp3_path: Path,
    spoken_text: str,
    bitrate: str,
    settings: Settings,
) -> None:
    """Prepend a macOS spoken intro to an MP3 file in place."""
    if not shutil.which("say"):
        raise RuntimeError(
            "Voice announcements require macOS (`say`). "
            "Set SHOCKZ_ANNOUNCE=false or pass --no-announce to skip."
        )
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required for voice announcements.")

    spoken_text = spoken_text.strip()
    if not spoken_text:
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        intro_aiff = tmp_dir / "intro.aiff"
        intro_mp3 = tmp_dir / "intro.mp3"
        pause_mp3 = tmp_dir / "pause.mp3"
        merged_mp3 = tmp_dir / "merged.mp3"

        run_command(["say", "-v", settings.announce_voice, "-o", str(intro_aiff), spoken_text])
        run_command(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(intro_aiff),
                "-ar",
                "44100",
                "-ac",
                "2",
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "128k",
                str(intro_mp3),
            ]
        )
        run_command(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=44100:cl=stereo",
                "-t",
                str(settings.announce_pause_sec),
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "128k",
                str(pause_mp3),
            ]
        )
        run_command(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(intro_mp3),
                "-i",
                str(pause_mp3),
                "-i",
                str(mp3_path),
                "-filter_complex",
                "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]",
                "-map",
                "[out]",
                "-codec:a",
                "libmp3lame",
                "-b:a",
                f"{bitrate}k",
                str(merged_mp3),
            ]
        )
        shutil.copyfile(merged_mp3, mp3_path)
