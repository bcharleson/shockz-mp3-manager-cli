#!/usr/bin/env python3
"""
Shokz MP3 manager — extract YouTube audio into a local library, sync flat to headset.
"""

import shutil
import sys
from pathlib import Path

import click
import yt_dlp
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()

LIBRARY_DIR = Path.home() / "Documents" / "mp3-songs"
SHOKZ_VOLUME = Path("/Volumes/SWIM PRO")
SUPPORTED_BITRATES = ["128", "192", "256", "320"]
DEFAULT_BITRATE = "320"


def shokz_connected() -> bool:
    return SHOKZ_VOLUME.is_dir()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def library_files() -> list[Path]:
    ensure_dir(LIBRARY_DIR)
    return sorted(
        path
        for path in LIBRARY_DIR.glob("*.mp3")
        if path.is_file() and not path.name.startswith("._")
    )


def resolve_library_files(names: tuple[str, ...]) -> list[Path]:
    if not names:
        return library_files()

    available = {path.name: path for path in library_files()}
    selected: list[Path] = []

    for name in names:
        if name in available:
            selected.append(available[name])
            continue

        matches = [path for path in available.values() if name.lower() in path.name.lower()]
        if len(matches) == 1:
            selected.append(matches[0])
            continue
        if len(matches) > 1:
            console.print(f"[bold red]Ambiguous match for[/bold red] {name!r}:")
            for match in matches:
                console.print(f"  - {match.name}")
            sys.exit(1)

        console.print(f"[bold red]Not found in library:[/bold red] {name}")
        sys.exit(1)

    return selected


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


def extract(url: str, output_dir: Path, bitrate: str, filename: str | None) -> dict:
    options = build_ydl_options(output_dir, bitrate, filename)
    with yt_dlp.YoutubeDL(options) as ydl:
        return ydl.extract_info(url, download=True)


def output_path(info: dict, output_dir: Path, filename: str | None) -> Path:
    if filename:
        return output_dir / f"{filename}.mp3"
    title = info.get("title", "download")
    return output_dir / f"{title}.mp3"


def copy_to_shokz(source: Path, destination: Path) -> None:
    """Copy MP3 data only — Shokz uses FAT, which rejects macOS metadata/flags."""
    shutil.copyfile(source, destination)


def sync_files(files: list[Path]) -> list[Path]:
    if not shokz_connected():
        console.print("[bold red]SWIM PRO not connected.[/bold red] Plug in your Shokz and try again.")
        sys.exit(1)

    copied: list[Path] = []
    for source in files:
        destination = SHOKZ_VOLUME / source.name
        copy_to_shokz(source, destination)
        copied.append(destination)

    return copied


def print_track_table(info: dict, library_path: Path, bitrate: str, synced: bool) -> None:
    title = info.get("title", "Unknown")
    duration_secs = info.get("duration", 0)
    minutes, seconds = divmod(duration_secs, 60)
    uploader = info.get("uploader", "Unknown")

    table = Table(title="Extraction Complete", border_style="green", show_header=False)
    table.add_column("Field", style="bold cyan")
    table.add_column("Value", style="white")
    table.add_row("Title", title)
    table.add_row("Uploader", uploader)
    table.add_row("Duration", f"{minutes}m {seconds}s")
    table.add_row("Bitrate", f"{bitrate} kbps")
    table.add_row("Library", str(library_path))
    table.add_row("On headset", "Yes — SWIM PRO root" if synced else "No — run `sync` when connected")
    console.print(table)


@click.group()
def cli() -> None:
    """Manage a local MP3 library and sync tracks to Shokz (flat, root-level only)."""


@cli.command()
@click.argument("url")
@click.option(
    "--bitrate",
    "-b",
    default=DEFAULT_BITRATE,
    type=click.Choice(SUPPORTED_BITRATES),
    show_default=True,
    help="MP3 bitrate in kbps.",
)
@click.option(
    "--filename",
    "-f",
    default=None,
    help="Custom library filename (without extension). Defaults to video title.",
)
@click.option(
    "--sync/--no-sync",
    default=None,
    help="Copy to headset after download. Defaults to sync when SWIM PRO is connected.",
)
def extract_cmd(url: str, bitrate: str, filename: str | None, sync: bool | None) -> None:
    """Download a YouTube URL into ~/Documents/mp3-songs."""
    should_sync = shokz_connected() if sync is None else sync
    ensure_dir(LIBRARY_DIR)

    device_status = (
        "[green]SWIM PRO connected[/green]"
        if shokz_connected()
        else "[yellow]SWIM PRO not connected[/yellow]"
    )
    sync_status = (
        "[green]will sync to headset[/green]"
        if should_sync and shokz_connected()
        else "[dim]library only[/dim]"
    )

    console.print(
        Panel(
            f"[bold]YouTube → MP3[/bold]\n"
            f"URL: [cyan]{url}[/cyan]\n"
            f"Library: [yellow]{LIBRARY_DIR}[/yellow]\n"
            f"Bitrate: [green]{bitrate} kbps[/green]\n"
            f"Device: {device_status}\n"
            f"After download: {sync_status}",
            title="[bold magenta]Shokz MP3 Manager[/bold magenta]",
            border_style="magenta",
        )
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Downloading and converting...", total=None)
        try:
            info = extract(url, LIBRARY_DIR, bitrate, filename)
            progress.update(task, completed=True, description="Done")
        except yt_dlp.utils.DownloadError as exc:
            console.print(f"[bold red]Download failed:[/bold red] {exc}")
            sys.exit(1)

    library_path = output_path(info, LIBRARY_DIR, filename)
    synced = False
    if should_sync and library_path.exists():
        sync_files([library_path])
        synced = True

    print_track_table(info, library_path, bitrate, synced)


@cli.command()
@click.argument("files", nargs=-1)
def sync(files: tuple[str, ...]) -> None:
    """Copy library MP3s to the Shokz root (no subfolders)."""
    selected = resolve_library_files(files)
    if not selected:
        console.print(f"[yellow]Library is empty:[/yellow] {LIBRARY_DIR}")
        sys.exit(0)

    copied = sync_files(selected)
    console.print(f"\n[bold green]Synced {len(copied)} file(s) to SWIM PRO root[/bold green]")
    for path in copied:
        console.print(f"  [cyan]{path.name}[/cyan]")
    console.print("\nEject when done: [dim]diskutil eject '/Volumes/SWIM PRO'[/dim]\n")


@cli.command("list")
def list_cmd() -> None:
    """Show MP3s in the local library."""
    files = library_files()
    if not files:
        console.print(f"[yellow]No MP3s yet.[/yellow] Library: {LIBRARY_DIR}")
        return

    table = Table(title=f"Library ({len(files)} tracks)", border_style="cyan")
    table.add_column("#", style="dim")
    table.add_column("Filename")
    table.add_column("Size", justify="right")

    for index, path in enumerate(files, start=1):
        size_mb = path.stat().st_size / (1024 * 1024)
        table.add_row(str(index), path.name, f"{size_mb:.1f} MB")

    console.print(table)
    console.print(f"\nLibrary: [yellow]{LIBRARY_DIR}[/yellow]")
    if shokz_connected():
        console.print("Headset: [green]SWIM PRO connected[/green] — run [cyan]python extractor.py sync[/cyan]")
    else:
        console.print("Headset: [yellow]not connected[/yellow]")


if __name__ == "__main__":
    cli()
