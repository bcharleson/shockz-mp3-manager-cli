"""Runtime configuration from environment variables."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

_CONFIG_LOADED = False


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", line)
        if not match:
            continue
        key, value = match.group(1), _strip_quotes(match.group(2).strip())
        os.environ.setdefault(key, value)


def load_env_files() -> None:
    """Load optional env files without overriding existing variables."""
    global _CONFIG_LOADED
    if _CONFIG_LOADED:
        return
    _CONFIG_LOADED = True

    candidates: list[Path] = []
    if custom := os.environ.get("SHOCKZ_ENV_FILE"):
        candidates.append(Path(custom).expanduser())
    candidates.append(Path.cwd() / ".env")
    candidates.append(Path.home() / ".config" / "shockz-mp3-manager" / ".env")

    for path in candidates:
        _load_env_file(path)


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
    load_env_files()
    return Settings.from_env()
