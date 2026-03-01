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
from pathlib import Path

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
    files: list[str] = typer.Argument(..., help="Path(s) to text file(s) to ingest."),
):
    """Ingest one or more text files into the vault."""
    from backend.ingest import ingest_file, DuplicateError, get_ingest_queue

    # Resolve and validate all paths first
    resolved: list[Path] = []
    for f in files:
        fp = Path(f).resolve()
        if not fp.exists():
            console.print(f"[red]❌ File not found:[/red] {fp}")
            continue
        resolved.append(fp)

    if not resolved:
        console.print("[red]❌ No valid files to ingest.[/red]")
        raise typer.Exit(code=1)

    import uuid
    import shutil
    import os
    
    VAULT_DIR = Path("blackvault_data/files").resolve()
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    
    vault_paths: list[tuple[str, Path]] = []
    for fp in resolved:
        safe_filename = fp.name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        vault_path = VAULT_DIR / f"{uuid.uuid4().hex}_{safe_filename}"
        shutil.copy2(fp, vault_path)
        vault_paths.append((str(vault_path), fp))

    # Single file — direct (backward-compatible behaviour)
    if len(resolved) == 1:
        vault_path_str, original_fp = vault_paths[0]
        try:
            logging.info(f"Ingesting file: {original_fp}")
            
            import mimetypes
            mime, _ = mimetypes.guess_type(vault_path_str)
            mime = mime or "application/octet-stream"
            
            if mime.startswith("image/"):
                from backend.ocr import extract_text_from_image
                parsed_text = extract_text_from_image(vault_path_str)
            else:
                try:
                    parsed_text = Path(vault_path_str).read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    raise ValueError("File encoding error. Must be UTF-8.")
                    
            item_id = ingest_file(vault_path_str, parsed_text=parsed_text)
            logging.info(f"Successfully ingested item #{item_id}")
            console.print(
                Panel(
                    f"[green]Item #{item_id}[/green] stored successfully.\n"
                    f"Source: {original_fp}\n"
                    f"Vault Path: {vault_path_str}",
                    title="✅ Ingested",
                    border_style="green",
                )
            )
        except DuplicateError as e:
            if os.path.exists(vault_path_str):
                os.remove(vault_path_str)
            console.print(
                Panel(
                    f"[yellow]Item #{e.existing_id}[/yellow] already exists.\n"
                    f"Skipping ingestion to save resources.\n"
                    f"Source: {original_fp}",
                    title="⚠️  Duplicate Detected",
                    border_style="yellow",
                )
            )
        except ValueError as e:
            if os.path.exists(vault_path_str):
                os.remove(vault_path_str)
            console.print(f"[red]❌ {e}[/red]")
            raise typer.Exit(code=1)
        except Exception as e:
            if os.path.exists(vault_path_str):
                os.remove(vault_path_str)
            console.print(f"[red]❌ {e}[/red]")
            raise typer.Exit(code=1)
        return

    # Multiple files — parallel via IngestQueue
    console.print(f"[bold]📦 Queuing {len(resolved)} file(s) for parallel ingestion...[/bold]\n")
    queue = get_ingest_queue()
    queue.submit_batch([vp for vp, _ in vault_paths])
    results = queue.drain()

    # Summary table
    table = Table(title="📊 Ingestion Summary", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("File", style="bold")
    table.add_column("Status")
    table.add_column("ID", width=6)

    ingested = duplicates = errors = 0
    # Map back the vault paths to original paths for display
    # Results come out in same order as submitted queue
    for i, (r, (_, orig_fp)) in enumerate(zip(results, vault_paths), 1):
        name = orig_fp.name
        if r.is_duplicate:
            duplicates += 1
            table.add_row(str(i), name, "[yellow]⚠️  Duplicate[/yellow]", str(r.duplicate_id))
            if os.path.exists(r.path):
                os.remove(r.path)
        elif r.success:
            ingested += 1
            table.add_row(str(i), name, "[green]✅ OK[/green]", str(r.item_id))
        else:
            errors += 1
            table.add_row(str(i), name, f"[red]❌ {r.error}[/red]", "—")
            if os.path.exists(r.path):
                os.remove(r.path)

    console.print(table)
    console.print(
        f"\n[bold]Total:[/bold] {len(results)} | "
        f"[green]Ingested:[/green] {ingested} | "
        f"[yellow]Duplicates:[/yellow] {duplicates} | "
        f"[red]Errors:[/red] {errors}"
    )


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
