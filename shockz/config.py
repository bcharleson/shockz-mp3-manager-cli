"""Runtime configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _expand_path(value: str) -> Path:
    return Path(os.path.expanduser(value)).resolve()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    library_dir: Path
    device_path: Path
    pool_filename: str
    announce_enabled: bool
    announce_voice: str
    announce_pause_sec: float
    default_bitrate: str
    recommended_max_tracks: int
    supported_bitrates: tuple[str, ...]

    @property
    def pool_file(self) -> Path:
        return self.library_dir / self.pool_filename

    @classmethod
    def from_env(cls) -> Settings:
        library = _expand_path(
            os.environ.get("SHOCKZ_LIBRARY_DIR", "~/Music/shockz-library")
        )
        return cls(
            library_dir=library,
            device_path=_expand_path(
                os.environ.get("SHOCKZ_DEVICE_PATH", "/Volumes/SWIM PRO")
            ),
            pool_filename=os.environ.get("SHOCKZ_POOL_FILE", ".on-device.txt"),
            announce_enabled=_env_bool("SHOCKZ_ANNOUNCE", True),
            announce_voice=os.environ.get("SHOCKZ_ANNOUNCE_VOICE", "Samantha"),
            default_bitrate=os.environ.get("SHOCKZ_DEFAULT_BITRATE", "320"),
            announce_pause_sec=float(os.environ.get("SHOCKZ_ANNOUNCE_PAUSE_SEC", "0.35")),
            recommended_max_tracks=int(os.environ.get("SHOCKZ_RECOMMENDED_MAX_TRACKS", "10")),
            supported_bitrates=("128", "192", "256", "320"),
        )


def get_settings() -> Settings:
    return Settings.from_env()
