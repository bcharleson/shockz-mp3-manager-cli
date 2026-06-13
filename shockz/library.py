"""Library archive and active-pool management."""

from __future__ import annotations

from pathlib import Path

from shockz.config import Settings


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def library_files(settings: Settings) -> list[Path]:
    ensure_dir(settings.library_dir)
    return sorted(
        path
        for path in settings.library_dir.glob("*.mp3")
        if path.is_file() and not path.name.startswith("._")
    )


def read_pool_names(settings: Settings) -> list[str]:
    ensure_dir(settings.library_dir)
    pool_file = settings.pool_file
    if not pool_file.exists():
        return []
    return [
        line.strip()
        for line in pool_file.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def write_pool_names(settings: Settings, names: list[str]) -> None:
    ensure_dir(settings.library_dir)
    unique = sorted(set(names))
    settings.pool_file.write_text("\n".join(unique) + ("\n" if unique else ""))


def add_to_pool(settings: Settings, name: str) -> None:
    names = read_pool_names(settings)
    if name not in names:
        names.append(name)
    write_pool_names(settings, names)


def remove_from_pool(settings: Settings, name: str) -> None:
    write_pool_names(settings, [entry for entry in read_pool_names(settings) if entry != name])


def pool_paths(settings: Settings) -> list[Path]:
    return [
        settings.library_dir / name
        for name in read_pool_names(settings)
        if (settings.library_dir / name).exists()
    ]


def archive_paths(settings: Settings) -> list[Path]:
    pool_names = set(read_pool_names(settings))
    return [path for path in library_files(settings) if path.name not in pool_names]
