"""Clipper command-line interface."""

from __future__ import annotations

import json
from typing import Any

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

from app import paths
from app.core import registry
from app.pipeline import analysis_graph, render_graph
from app.run import project_id_for, run_graph

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Modular video clipper.")
console = Console()


class ConsoleEmitter:
    """Renders graph events as a live single-bar progress display."""

    def __init__(self) -> None:
        self.progress = Progress(
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(bar_width=36),
            TextColumn("{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
            transient=False,
        )
        self.task: int | None = None

    def __enter__(self) -> ConsoleEmitter:
        self.progress.start()
        self.task = self.progress.add_task("starting", total=100)
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.progress.stop()

    def __call__(self, type: str, node: str | None = None, pct: float | None = None,
                 message: str = "", level: str = "info", **_kw: Any) -> None:
        assert self.task is not None
        label = message or (node or "")
        if type == "start":
            self.progress.update(self.task, description=f"> {label}", completed=0)
        elif type == "progress" and pct is not None:
            self.progress.update(
                self.task, description=f"  {label or 'working'}", completed=pct * 100
            )
        elif type == "done":
            self.progress.update(self.task, description=f"ok {label}", completed=100)
        elif type == "log":
            style = "yellow" if level == "warn" else "red" if level == "error" else "dim"
            console.print(f"    {message}", style=style, highlight=False)


def _analyze(
    source: str,
    project: str | None,
    n_clips: int,
    min_duration: int,
    max_duration: int,
    cookies: str | None,
) -> None:
    pid = project_id_for(source, project)
    graph = analysis_graph(
        pid, source, n_clips=n_clips, min_duration=min_duration,
        max_duration=max_duration, cookies_from_browser=cookies,
    )
    with ConsoleEmitter() as emit:
        results, ctx = run_graph(graph, pid, emit=emit)
    export = results.get("export", {})
    console.print("\n[bold green]Analysis complete[/bold green]")
    console.print(f"  project : {ctx.project.root}")
    console.print(f"  payload : {export.get('payload_txt')}  [dim](paste this to your AI)[/dim]")
    console.print(f"  prompt  : {export.get('prompt_txt')}  [dim](paste this too)[/dim]")


def _render(
    source: str,
    project: str | None,
    clips: str | None,
    inline: str | None,
    style: str | None,
    reframe: str,
    track: bool,
    lut: str | None,
    music: str | None,
    platform: str,
    titles: bool,
) -> None:
    pid = project_id_for(source, project)
    graph = render_graph(
        pid, source, clips_path=clips, clips_inline=inline,
        caption_style=style, reframe=reframe, track_subjects=track,
        lut=lut, music=music, platform=platform, add_titles=titles,
    )
    with ConsoleEmitter() as emit:
        results, ctx = run_graph(graph, pid, emit=emit)
    renders = results.get("render", {}).get("renders", [])
    console.print("\n[bold green]Renders[/bold green]")
    for item in renders:
        console.print(f"  {item['clip_id']:<12} {item['duration']:>6.1f}s  {item['path']}")
    meta = results.get("metadata", {}).get("metadata_file")
    if meta:
        console.print(f"  [dim]metadata: {meta}[/dim]")


@app.command()
def analyze(
    source: str = typer.Argument(..., help="Video URL or local file path"),
    project: str | None = typer.Option(None, help="Project id (defaults to a slug of the source)"),
    n_clips: int = typer.Option(8, help="How many clips to ask the AI for"),
    min_duration: int = typer.Option(15, help="Minimum clip seconds"),
    max_duration: int = typer.Option(60, help="Maximum clip seconds"),
    cookies: str | None = typer.Option(None, help="yt-dlp --cookies-from-browser value, e.g. chrome"),
) -> None:
    """Download, transcribe and export the AI payload + prompt."""
    _analyze(source, project, n_clips, min_duration, max_duration, cookies)


@app.command()
def render(
    source: str = typer.Argument(..., help="Video URL or local file path"),
    clips: str | None = typer.Option(None, help="Path to the AI's clips.json / .csv"),
    inline: str | None = typer.Option(None, help="Raw clips JSON/CSV string"),
    project: str | None = typer.Option(None, help="Project id"),
    style: str | None = typer.Option(None, help="Caption style (see `clipper styles`)"),
    reframe: str = typer.Option("auto", help="auto | crop | blur | pad"),
    lut: str | None = typer.Option(None, help="LUT name from assets/luts (no extension) or a path"),
    music: str | None = typer.Option(None, help="Music name from assets/music or a path"),
    platform: str = typer.Option("shorts", help="shorts | reels | tiktok (caption safe area)"),
    titles: bool = typer.Option(True, "--titles/--no-titles", help="Burn a title card per clip"),
    track: bool = typer.Option(True, "--track/--no-track", help="Track the subject (needs ml extra)"),
) -> None:
    """Ingest, import clips, refine, caption, track and render final vertical videos."""
    _render(source, project, clips, inline, style, reframe, track, lut, music, platform, titles)


@app.command()
def styles() -> None:
    """List built-in caption styles."""
    from app.config import CAPTION_PRESETS

    table = Table(title="Caption styles")
    table.add_column("key", style="bold")
    table.add_column("label")
    table.add_column("font")
    table.add_column("mode")
    for key, preset in CAPTION_PRESETS.items():
        table.add_row(key, preset.label, preset.font, preset.mode)
    console.print(table)


@app.command()
def nodes() -> None:
    """List available node types (the canvas palette)."""
    table = Table(title="Node catalog")
    table.add_column("type", style="bold")
    table.add_column("title")
    table.add_column("category")
    table.add_column("inputs")
    table.add_column("outputs")
    for item in registry.catalog():
        table.add_row(
            item["type"], item["title"], item["category"],
            ", ".join(item["inputs"]) or "-", ", ".join(item["outputs"]) or "-",
        )
    console.print(table)


@app.command()
def graph(
    stage: str = typer.Argument("analysis", help="analysis | render"),
    source: str = typer.Option(..., help="Video URL or path"),
    project: str | None = typer.Option(None),
) -> None:
    """Print a pipeline graph as JSON (what the UI canvas renders)."""
    pid = project_id_for(source, project)
    g = analysis_graph(pid, source) if stage == "analysis" else render_graph(pid, source)
    console.print_json(json.dumps(g.to_dict()))


@app.command()
def toolcheck() -> None:
    """Verify the local toolchain is available."""
    for name, fn in (("ffmpeg", paths.ffmpeg), ("ffprobe", paths.ffprobe), ("yt-dlp", paths.ytdlp)):
        try:
            console.print(f"  {name:<8} [green]ok[/green] {fn()}")
        except FileNotFoundError as exc:
            console.print(f"  {name:<8} [red]missing[/red] {exc}")


if __name__ == "__main__":
    app()
