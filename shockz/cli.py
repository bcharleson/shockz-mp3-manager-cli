#!/usr/bin/env python3
"""CLI for Shokz MP3 Manager."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import yt_dlp
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from shockz import __version__
from shockz.audio import extract_url, output_path, prepend_voice_announcement
from shockz.config import Settings, get_settings
from shockz.device import (
    device_connected,
    device_free_bytes,
    device_label,
    device_paths,
    format_bytes,
    prune_device,
    sync_files,
)
from shockz.labels import spoken_label_for_track, to_spoken_label
from shockz.library import (
    add_to_pool,
    archive_paths,
    ensure_dir,
    library_files,
    pool_paths,
    read_pool_names,
    remove_from_pool,
)

console = Console()


def resolve_library_files(settings: Settings, names: tuple[str, ...]) -> list[Path]:
    if not names:
        return library_files(settings)

    available = {path.name: path for path in library_files(settings)}
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


def require_device(settings: Settings) -> None:
    if not device_connected(settings):
        label = device_label(settings)
        console.print(
            f"[bold red]{label} not connected.[/bold red] "
            "Plug in your Shokz and try again."
        )
        sys.exit(1)


def sync_or_exit(settings: Settings, files: list[Path]) -> list[Path]:
    require_device(settings)
    return sync_files(settings, files)


def apply_announcement(
    mp3_path: Path,
    spoken_text: str,
    bitrate: str,
    settings: Settings,
    *,
    show_progress: bool = True,
) -> None:
    if show_progress:
        console.print(f"[cyan]Announcing:[/cyan] \"{spoken_text}\"")
    prepend_voice_announcement(mp3_path, spoken_text, bitrate, settings)


def print_track_table(
    info: dict,
    library_path: Path,
    bitrate: str,
    synced: bool,
    settings: Settings,
    spoken: str | None = None,
) -> None:
    title = info.get("title", "Unknown")
    duration_secs = info.get("duration", 0)
    minutes, seconds = divmod(duration_secs, 60)
    uploader = info.get("uploader", "Unknown")
    device_name = device_label(settings)

    table = Table(title="Extraction Complete", border_style="green", show_header=False)
    table.add_column("Field", style="bold cyan")
    table.add_column("Value", style="white")
    table.add_row("Title", title)
    table.add_row("Uploader", uploader)
    table.add_row("Duration", f"{minutes}m {seconds}s")
    table.add_row("Bitrate", f"{bitrate} kbps")
    if spoken:
        table.add_row("Voice intro", f'"{spoken}"')
    table.add_row("Library", str(library_path))
    table.add_row(
        "On headset",
        f"Yes — {device_name} root" if synced else "No — run `shockz sync` when connected",
    )
    console.print(table)


@click.group()
@click.version_option(__version__, prog_name="shockz")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Manage a local MP3 library and sync tracks to Shokz (flat, root-level only)."""
    ctx.ensure_object(dict)
    ctx.obj["settings"] = get_settings()


@cli.command()
@click.argument("url")
@click.option(
    "--bitrate",
    "-b",
    default=None,
    type=click.Choice(["128", "192", "256", "320"]),
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
    help="Copy to headset after download. Defaults to sync when the device is connected.",
)
@click.option(
    "--archive",
    is_flag=True,
    help="Save to library only — do not add to the active pool or copy to the headset.",
)
@click.option(
    "--announce",
    "-a",
    "announce",
    default=None,
    help="Spoken intro before the track. Defaults from title/filename.",
)
@click.option(
    "--no-announce",
    is_flag=True,
    help="Skip the spoken intro at the start of the track.",
)
@click.pass_context
def extract_cmd(
    ctx: click.Context,
    url: str,
    bitrate: str | None,
    filename: str | None,
    sync: bool | None,
    archive: bool,
    announce: str | None,
    no_announce: bool,
) -> None:
    """Download a YouTube URL into your local library."""
    settings: Settings = ctx.obj["settings"]
    bitrate = bitrate or settings.default_bitrate
    connected = device_connected(settings)
    should_sync = False if archive else (connected if sync is None else sync)
    should_announce = settings.announce_enabled and not no_announce
    ensure_dir(settings.library_dir)

    if should_announce:
        if announce:
            intro_preview = announce
        elif filename:
            intro_preview = to_spoken_label(filename)
        else:
            intro_preview = None
        announce_status = (
            f'[green]voice intro[/green] — "{intro_preview}"'
            if intro_preview
            else "[green]voice intro[/green] — auto from title"
        )
    else:
        announce_status = "[dim]no voice intro[/dim]"

    device_name = device_label(settings)
    device_status = (
        f"[green]{device_name} connected[/green]"
        if connected
        else f"[yellow]{device_name} not connected[/yellow]"
    )
    sync_status = (
        "[green]active pool + headset[/green]"
        if should_sync and connected
        else "[yellow]archive only[/yellow]"
        if archive
        else "[cyan]active pool[/cyan] (sync later)"
        if not should_sync
        else "[dim]library only[/dim]"
    )

    console.print(
        Panel(
            f"[bold]YouTube → MP3[/bold]\n"
            f"URL: [cyan]{url}[/cyan]\n"
            f"Library: [yellow]{settings.library_dir}[/yellow]\n"
            f"Bitrate: [green]{bitrate} kbps[/green]\n"
            f"Device: {device_status}\n"
            f"After download: {sync_status}\n"
            f"Intro: {announce_status}",
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
            info = extract_url(url, settings.library_dir, bitrate, filename)
            progress.update(task, completed=True, description="Done")
        except yt_dlp.utils.DownloadError as exc:
            console.print(f"[bold red]Download failed:[/bold red] {exc}")
            sys.exit(1)

    library_path = output_path(info, settings.library_dir, filename)
    spoken_text: str | None = None

    if should_announce and library_path.exists():
        spoken_text = spoken_label_for_track(
            info.get("title", "track"),
            filename,
            announce,
        )
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Adding voice intro...", total=None)
            try:
                apply_announcement(
                    library_path,
                    spoken_text,
                    bitrate,
                    settings,
                    show_progress=False,
                )
                progress.update(task, completed=True, description="Intro added")
            except RuntimeError as exc:
                console.print(f"[bold red]Voice intro failed:[/bold red] {exc}")
                sys.exit(1)

    synced = False
    if library_path.exists() and not archive:
        add_to_pool(settings, library_path.name)
    if should_sync and library_path.exists():
        sync_or_exit(settings, [library_path])
        synced = True

    print_track_table(info, library_path, bitrate, synced, settings, spoken_text)


@cli.command()
@click.argument("files", nargs=-1)
@click.option(
    "--announce",
    "-a",
    "announce",
    default=None,
    help="Custom spoken line. Defaults from each filename.",
)
@click.option(
    "--bitrate",
    "-b",
    default=None,
    type=click.Choice(["128", "192", "256", "320"]),
    help="MP3 bitrate when re-encoding with the intro.",
)
@click.option(
    "--sync/--no-sync",
    default=True,
    show_default=True,
    help="Copy updated files to the headset after adding intros.",
)
@click.pass_context
def announce_cmd(
    ctx: click.Context,
    files: tuple[str, ...],
    announce: str | None,
    bitrate: str | None,
    sync: bool,
) -> None:
    """Add a spoken intro to existing library tracks."""
    settings: Settings = ctx.obj["settings"]
    bitrate = bitrate or settings.default_bitrate
    selected = resolve_library_files(settings, files)
    if not selected:
        console.print(f"[yellow]Library is empty:[/yellow] {settings.library_dir}")
        sys.exit(0)

    updated: list[Path] = []
    for path in selected:
        spoken = announce.strip() if announce else to_spoken_label(path.name)
        try:
            apply_announcement(path, spoken, bitrate, settings)
            updated.append(path)
        except RuntimeError as exc:
            console.print(f"[bold red]Failed for[/bold red] {path.name}: {exc}")
            sys.exit(1)

    console.print(f"\n[bold green]Added voice intro to {len(updated)} track(s)[/bold green]")
    if sync and updated:
        if device_connected(settings):
            sync_or_exit(settings, updated)
            console.print(f"[green]Synced updated tracks to {device_label(settings)}[/green]")
        else:
            console.print("[yellow]Headset not connected — run `shockz sync` when ready[/yellow]")
    console.print()


@cli.command()
@click.argument("files", nargs=-1)
@click.option(
    "--all",
    "sync_all",
    is_flag=True,
    help="Sync the entire library, not just the active pool.",
)
@click.option(
    "--prune",
    is_flag=True,
    help="Remove headset tracks that are not in the active pool.",
)
@click.pass_context
def sync(ctx: click.Context, files: tuple[str, ...], sync_all: bool, prune: bool) -> None:
    """Copy active-pool MP3s to the Shokz root (flat, no folders)."""
    settings: Settings = ctx.obj["settings"]
    if files:
        selected = resolve_library_files(settings, files)
    elif sync_all:
        selected = library_files(settings)
    else:
        selected = pool_paths(settings)

    if not selected and not prune:
        console.print(
            "[yellow]Nothing to sync.[/yellow] Active pool is empty — use [cyan]pool add[/cyan] "
            "or [cyan]extract[/cyan] without [cyan]--archive[/cyan]."
        )
        console.print(f"Pool file: [dim]{settings.pool_file}[/dim]")
        sys.exit(0)

    copied: list[Path] = []
    if selected:
        copied = sync_or_exit(settings, selected)

    removed: list[str] = []
    if prune:
        keep_names = (
            {path.name for path in selected}
            if selected
            else set(read_pool_names(settings))
        )
        removed = prune_device(settings, keep_names)

    device_name = device_label(settings)
    if copied:
        console.print(f"\n[bold green]Synced {len(copied)} file(s) to {device_name} root[/bold green]")
        for path in copied:
            console.print(f"  [cyan]{path.name}[/cyan]")
    if removed:
        console.print(f"\n[bold yellow]Removed {len(removed)} track(s) from headset[/bold yellow]")
        for name in removed:
            console.print(f"  [dim]{name}[/dim]")
    if not copied and not removed:
        console.print("[green]Headset already matches the active pool.[/green]")

    console.print(f"\nEject when done: [dim]diskutil eject '{settings.device_path}'[/dim]\n")


@cli.group()
def pool() -> None:
    """Manage the active pool — tracks that belong on the headset."""


@pool.command("list")
@click.pass_context
def pool_list(ctx: click.Context) -> None:
    """Show tracks in the active pool vs archive-only."""
    settings: Settings = ctx.obj["settings"]
    library = library_files(settings)
    active_names = set(read_pool_names(settings))
    if not library:
        console.print(f"[yellow]Library is empty:[/yellow] {settings.library_dir}")
        return

    table = Table(title="Library", border_style="cyan")
    table.add_column("#", style="dim")
    table.add_column("Track")
    table.add_column("On headset", justify="center")
    table.add_column("Size", justify="right")

    for index, path in enumerate(library, start=1):
        on_device = "yes" if path.name in active_names else "archive"
        size_mb = path.stat().st_size / (1024 * 1024)
        table.add_row(str(index), path.name, on_device, f"{size_mb:.1f} MB")

    console.print(table)
    active_count = len(
        [name for name in active_names if (settings.library_dir / name).exists()]
    )
    archive_count = len(library) - active_count
    console.print(
        f"\n[green]{active_count} active[/green] · [dim]{archive_count} archive-only[/dim] · "
        f"{len(library)} total"
    )
    max_tracks = settings.recommended_max_tracks
    if active_count > max_tracks:
        console.print(
            f"[yellow]Tip:[/yellow] {active_count} active tracks — consider keeping "
            f"~{max_tracks} or fewer for easier skip/back on the headset."
        )
    console.print(f"Pool file: [dim]{settings.pool_file}[/dim]")


@pool.command("add")
@click.argument("files", nargs=-1, required=True)
@click.pass_context
def pool_add(ctx: click.Context, files: tuple[str, ...]) -> None:
    """Add track(s) to the active pool."""
    settings: Settings = ctx.obj["settings"]
    selected = resolve_library_files(settings, files)
    for path in selected:
        add_to_pool(settings, path.name)
    console.print(f"[green]Added {len(selected)} track(s) to the active pool[/green]")


@pool.command("remove")
@click.argument("files", nargs=-1, required=True)
@click.pass_context
def pool_remove(ctx: click.Context, files: tuple[str, ...]) -> None:
    """Remove track(s) from the active pool (stays in archive)."""
    settings: Settings = ctx.obj["settings"]
    selected = resolve_library_files(settings, files)
    for path in selected:
        remove_from_pool(settings, path.name)
    console.print(
        f"[yellow]Removed {len(selected)} track(s) from the active pool[/yellow] "
        "(still in library — run [cyan]sync --prune[/cyan] to take off headset)"
    )


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show archive, active pool, headset, and free space."""
    settings: Settings = ctx.obj["settings"]
    library = library_files(settings)
    active = pool_paths(settings)
    archive = archive_paths(settings)
    on_device = device_paths(settings)
    active_names = {path.name for path in active}
    device_names = {path.name for path in on_device}
    library_bytes = sum(path.stat().st_size for path in library)
    active_bytes = sum(path.stat().st_size for path in active)
    device_bytes = sum(path.stat().st_size for path in on_device)
    free_bytes = device_free_bytes(settings)
    device_name = device_label(settings)

    table = Table(title="Storage overview", border_style="magenta", show_header=False)
    table.add_column("Location", style="bold cyan")
    table.add_column("Details", style="white")
    table.add_row(
        "Library",
        f"{settings.library_dir}\n{len(library)} tracks · {format_bytes(library_bytes)}",
    )
    table.add_row(
        "Active pool",
        f"{len(active)} tracks · {format_bytes(active_bytes)}\n{settings.pool_file}",
    )
    table.add_row(
        "Archive-only",
        f"{len(archive)} tracks kept for later (not in active pool)",
    )
    if device_connected(settings):
        free_label = format_bytes(free_bytes) if free_bytes is not None else "unknown"
        table.add_row(
            f"Shokz ({device_name})",
            f"{len(on_device)} tracks on device · {format_bytes(device_bytes)} used · "
            f"{free_label} free",
        )
    else:
        table.add_row(f"Shokz ({device_name})", "[yellow]not connected[/yellow]")

    console.print(table)

    if active_names != device_names and device_connected(settings):
        only_pool = sorted(active_names - device_names)
        only_device = sorted(device_names - active_names)
        if only_pool:
            console.print("\n[yellow]In active pool but not on headset:[/yellow]")
            for name in only_pool:
                console.print(f"  - {name}")
            console.print("Run [cyan]shockz sync[/cyan] to update the headset.")
        if only_device:
            console.print("\n[yellow]On headset but not in active pool:[/yellow]")
            for name in only_device:
                console.print(f"  - {name}")
            console.print("Run [cyan]shockz sync --prune[/cyan] to clean up.")

    max_tracks = settings.recommended_max_tracks
    if len(active) > max_tracks:
        console.print(
            f"\n[yellow]Heads up:[/yellow] {len(active)} active tracks. "
            f"~{max_tracks} or fewer keeps skip/back manageable in MP3 mode."
        )


@cli.command("list")
@click.pass_context
def list_cmd(ctx: click.Context) -> None:
    """Show MP3s in the local library."""
    settings: Settings = ctx.obj["settings"]
    files = library_files(settings)
    if not files:
        console.print(f"[yellow]No MP3s yet.[/yellow] Library: {settings.library_dir}")
        return

    table = Table(title=f"Library ({len(files)} tracks)", border_style="cyan")
    table.add_column("#", style="dim")
    table.add_column("Filename")
    table.add_column("Size", justify="right")

    for index, path in enumerate(files, start=1):
        size_mb = path.stat().st_size / (1024 * 1024)
        table.add_row(str(index), path.name, f"{size_mb:.1f} MB")

    console.print(table)
    console.print(f"\nLibrary: [yellow]{settings.library_dir}[/yellow]")
    device_name = device_label(settings)
    if device_connected(settings):
        console.print(
            f"Headset: [green]{device_name} connected[/green] — run [cyan]shockz sync[/cyan]"
        )
    else:
        console.print("Headset: [yellow]not connected[/yellow]")


@cli.command()
@click.pass_context
def config(ctx: click.Context) -> None:
    """Show effective configuration (paths and defaults)."""
    settings: Settings = ctx.obj["settings"]
    table = Table(title="Configuration", border_style="cyan", show_header=False)
    table.add_column("Setting", style="bold cyan")
    table.add_column("Value", style="white")
    table.add_row("Library directory", str(settings.library_dir))
    table.add_row("Active pool file", str(settings.pool_file))
    table.add_row("Device path", str(settings.device_path))
    table.add_row("Voice intros (SHOCKZ_ANNOUNCE)", "on" if settings.announce_enabled else "off")
    table.add_row("Announce voice", settings.announce_voice)
    table.add_row("Default bitrate", f"{settings.default_bitrate} kbps")
    table.add_row("Recommended max active tracks", str(settings.recommended_max_tracks))
    console.print(table)
    console.print(
        "\nOverride with environment variables — see [cyan].env.example[/cyan] in the repo."
    )


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
