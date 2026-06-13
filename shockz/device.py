"""Shokz device detection, sync, and copy helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

from shockz.config import Settings


def device_connected(settings: Settings) -> bool:
    return settings.device_path.is_dir()


def device_label(settings: Settings) -> str:
    return settings.device_path.name


def device_paths(settings: Settings) -> list[Path]:
    if not device_connected(settings):
        return []
    return sorted(
        path
        for path in settings.device_path.glob("*.mp3")
        if path.is_file() and not path.name.startswith("._")
    )


def device_free_bytes(settings: Settings) -> int | None:
    if not device_connected(settings):
        return None
    return shutil.disk_usage(settings.device_path).free


def format_bytes(num_bytes: int) -> str:
    if num_bytes >= 1024**3:
        return f"{num_bytes / 1024**3:.1f} GB"
    return f"{num_bytes / 1024**2:.0f} MB"


def copy_to_device(source: Path, destination: Path) -> None:
    """Copy MP3 data only — Shokz uses FAT, which rejects macOS metadata/flags."""
    shutil.copyfile(source, destination)


def sync_files(settings: Settings, files: list[Path]) -> list[Path]:
    copied: list[Path] = []
    for source in files:
        destination = settings.device_path / source.name
        copy_to_device(source, destination)
        copied.append(destination)
    return copied


def prune_device(settings: Settings, keep_names: set[str]) -> list[str]:
    removed: list[str] = []
    for path in device_paths(settings):
        if path.name in keep_names:
            continue
        path.unlink(missing_ok=True)
        removed.append(path.name)
    return removed
