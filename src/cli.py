"""
Black Vault — CLI interface.
Typer-based command-line interface that talks to the backend processor layer.

Usage:
    python cli.py ingest <file>
    python cli.py search "<query>"
    python cli.py list
    python cli.py show <id>
    python cli.py export [--format json|csv]
    python cli.py logtoggle
"""

from __future__ import annotations
#from backend/ingest import DuplicateError

import json
import csv
import sys
import io
import logging
import threading

# Force UTF-8 for Windows consoles to support Emojis
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
#import pytube

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

app = typer.Typer(
    name="blackvault",
    help="🕳️  Black Vault — Drop it, forget it, find it.",
    add_completion=False,
)
console = Console()


# ── Commands ─────────────────────────────────────────────────────────


@app.command()
def ingest(
    source: str = typer.Argument(..., help="Path to a text file OR a YouTube URL."),
):
    """Ingest a text file or YouTube video into the vault."""
    from backend.ingest import ingest_file, DuplicateError
    import re
    
    # ── Detectar si es URL de YouTube ───────────────────────────────
    def is_youtube_url(text: str) -> bool:
        pattern = r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+'
        return bool(re.match(pattern, text, re.IGNORECASE))

    # ── Lógica principal ───────────────────────────────────────────
    if is_youtube_url(source):
        from backend.youtube import get_video_info
        import re

        parsed_text = get_video_info(source)

        match = re.search(r"ID\s+:\s+(\S+)", parsed_text)
        video_id = match.group(1) if match else "unknown"
        
        youtube_dir = Path("youtube_videos")
        youtube_dir.mkdir(exist_ok=True)
        file_path = youtube_dir / f"yt_{video_id}.txt"

        try:
            file_path.write_text(parsed_text, encoding="utf-8")
            item_id = ingest_file(str(file_path), parsed_text)
            console.print(
                Panel(
                    f"[green]Item #{item_id}[/green] stored successfully.\n"
                    f"Source: {source}",
                    title="✅ YouTube Ingested",
                    border_style="green",
                )
            )
        except DuplicateError as e:
            console.print(
                Panel(
                    f"[yellow]Item #{e.existing_id}[/yellow] already exists.\n"
                    f"Skipping ingestion.\nSource: {source}",
                    title="⚠️  Duplicate Detected",
                    border_style="yellow",
                )
            )
            
    else:
        # 📁 Es archivo local
        filepath = Path(source).resolve()
        if not filepath.exists():
            console.print(f"[red]❌ File not found:[/red] {filepath}")
            raise typer.Exit(code=1)

        try:
            logging.info(f"Ingesting file: {filepath}")
            
            import mimetypes
            mime, _ = mimetypes.guess_type(str(filepath))
            mime = mime or "application/octet-stream"
            
            if mime.startswith("image/"):
                from backend.ocr import extract_text_from_image
                parsed_text = extract_text_from_image(str(filepath))
            elif mime == "application/pdf":
                from backend.pdf import extract_text_from_pdf
                parsed_text = extract_text_from_pdf(str(filepath))
            elif mime.startswith("audio/"):
                from backend.stt import extract_text_from_audio
                parsed_text = extract_text_from_audio(str(filepath))
            else:
                try:
                    parsed_text = filepath.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    raise ValueError("File encoding error. Must be UTF-8.")
                    
            item_id = ingest_file(str(filepath), parsed_text)
            logging.info(f"Successfully ingested item #{item_id}")
            console.print(
                Panel(
                    f"[green]Item #{item_id}[/green] stored successfully.\n"
                    f"Source: {filepath}",
                    title="✅ Ingested",
                    border_style="green",
                )
            )
            
        except DuplicateError as e:
            console.print(
                Panel(
                    f"[yellow]Item #{e.existing_id}[/yellow] already exists.\n"
                    f"Skipping ingestion to save resources.\n"
                    f"Source: {filepath}",
                    title="⚠️  Duplicate Detected",
                    border_style="yellow",
                )
            )
        except ValueError as e:
            console.print(f"[red]❌ {e}[/red]")
            raise typer.Exit(code=1)


@app.command()
def search(
    query: str = typer.Argument(..., help="Natural-language search query."),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results."),
):
    """Search the vault with natural language."""
    from backend.search import search as do_search

    logging.info(f"Searching for query: '{query}' (limit: {limit})")
    results = do_search(query, limit=limit)

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        raise typer.Exit()

    table = Table(title=f"🔍 Results for: \"{query}\"", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("ID", width=4)
    table.add_column("Title", style="bold")
    table.add_column("Score", justify="right", width=7)
    table.add_column("Snippet", max_width=60)

    for i, r in enumerate(results, 1):
        table.add_row(
            str(i),
            str(r["item_id"]),
            r.get("title", "—"),
            f"{r['score']:.3f}",
            r["snippet"][:120] + ("…" if len(r["snippet"]) > 120 else ""),
        )

    console.print(table)


@app.command(name="list")
def list_items():
    """List all items stored in the vault."""
    from backend.db import get_all_items

    logging.info("Listing all items in the vault")
    items = get_all_items()
    if not items:
        console.print("[yellow]The vault is empty.[/yellow]")
        raise typer.Exit()

    table = Table(title="📦 All Items", show_lines=True)
    table.add_column("ID", width=4)
    table.add_column("Title", style="bold")
    table.add_column("Type", width=6)
    table.add_column("Tags")
    table.add_column("Date", width=19)
    table.add_column("Enriched", width=4, justify="center")

    for item in items:
        table.add_row(
            str(item["id"]),
            item.get("title") or "(sin título)",
            item.get("source_type", "—"),
            item.get("tags") or "—",
            str(item.get("created_at", ""))[:19],
            "✅" if item.get("enriched") else "⏳",
        )

    console.print(table)


@app.command()
def show(
    item_id: int = typer.Argument(..., help="Item ID to display."),
):
    """Show details of a specific item, including connections."""
    from backend.db import get_item, get_chunks_for_item, log_item_view
    from backend.connections import get_connections

    logging.info(f"Showing details for item #{item_id}")
    item = get_item(item_id)
    if item is None:
        console.print(f"[red]❌ Item #{item_id} not found.[/red]")
        raise typer.Exit(code=1)
        
    # Log the view for session context
    log_item_view(item_id)

    # ── Item details ─────────────────────────────────────────────────
    title = item.get("title") or "(sin título)"
    meta = (
        f"[bold]{title}[/bold]\n\n"
        f"📁 Source:  {item.get('source_path', '—')}\n"
        f"🏷️  Tags:    {item.get('tags') or '—'}\n"
        f"📝 Summary: {item.get('summary') or '—'}\n"
        f"📅 Date:    {str(item.get('created_at', ''))[:19]}\n"
        f"✨ Enriched: {'Yes' if item.get('enriched') else 'No'}"
    )
    console.print(Panel(meta, title=f"Item #{item_id}", border_style="cyan"))

    # ── Content chunks ───────────────────────────────────────────────
    chunks = get_chunks_for_item(item_id)
    if chunks:
        console.print(f"\n[dim]── Content ({len(chunks)} chunk(s)) ──[/dim]")
        for ch in chunks:
            preview = ch["body"][:200]
            if len(ch["body"]) > 200:
                preview += "…"
            console.print(f"  [{ch['chunk_index']}] {preview}\n")

    # ── Connections ──────────────────────────────────────────────────
    conns = get_connections(item_id)
    if conns:
        console.print("[dim]── Related Items ──[/dim]")
        for c in conns:
            console.print(
                f"  🔗 #{c['item_id']} — {c['title']} "
                f"(similarity: {c['score']:.3f})"
            )
    else:
        console.print("[dim]No related items found.[/dim]")


@app.command(name="consolidate")
def consolidate():
    """Consolidate small similar notes into single documents."""
    from backend.consolidate import run_consolidation
    console.print("Starting note consolidation...")
    results = run_consolidation()
    if not results:
        console.print("[yellow]No notes were consolidated.[/yellow]")
        raise typer.Exit()
        
    for r in results:
        console.print(f"✅ Created [green]'{r['title']}'[/green] (Item #{r['new_id']}) by merging {r['merged_count']} notes.")



@app.command()
def export(
    format: str = typer.Option("json", "--format", "-f", help="Export format: json or csv."),
):
    """Export all items from the vault."""
    from backend.db import get_all_items, get_chunks_for_item

    logging.info(f"Exporting all items in format: {format}")
    items = get_all_items()
    if not items:
        console.print("[yellow]Nothing to export.[/yellow]")
        raise typer.Exit()

    # Attach full text to each item
    export_data = []
    for item in items:
        chunks = get_chunks_for_item(item["id"])
        full_text = "\n".join(c["body"] for c in chunks)
        item_export = {
            "id": item["id"],
            "title": item.get("title", ""),
            "source_path": item.get("source_path", ""),
            "source_type": item.get("source_type", ""),
            "tags": item.get("tags", ""),
            "summary": item.get("summary", ""),
            "created_at": str(item.get("created_at", "")),
            "full_text": full_text,
        }
        export_data.append(item_export)

    if format.lower() == "json":
        output = json.dumps(export_data, indent=2, ensure_ascii=False)
        print(output)
    elif format.lower() == "csv":
        if export_data:
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=export_data[0].keys())
            writer.writeheader()
            writer.writerows(export_data)
            console.print(buf.getvalue())
    else:
        console.print(f"[red]Unknown format: {format}. Use json or csv.[/red]")
        raise typer.Exit(code=1)

    console.print(f"\n[green]Exported {len(export_data)} item(s).[/green]")

@app.command()
def logtoggle():
    """Start or stop tracking operations to a log file."""
    from backend.log import toggle_logging
    
    enabled = toggle_logging()
    if enabled:
        console.print("[green]File logging started. Operations will be tracked.[/green]")
        logging.info("=== File logging started ===")
    else:
        logging.info("=== File logging stopped ===")
        console.print("[yellow]File logging stopped.[/yellow]")

@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose console logging."),
):
    from rich.logging import RichHandler
    from backend.log import setup_file_logging

    # Base logging setup for console (if verbose) or general info
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, console=console)],
    )
    
    # Attach persistent file handler if logging is enabled
    setup_file_logging()


# ── Entry point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
