from __future__ import annotations

import asyncio
import threading
import time
import webbrowser
from pathlib import Path

import click
import uvicorn


def _open_browser(url: str, delay: float = 1.5) -> None:
    """Open browser after a short delay in a daemon thread."""
    def _open() -> None:
        time.sleep(delay)
        webbrowser.open(url)

    t = threading.Thread(target=_open, daemon=True)
    t.start()


@click.group(invoke_without_command=True)
@click.pass_context
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind host")
@click.option("--port", default=8000, show_default=True, help="Bind port")
@click.option("--reload", is_flag=True, help="Enable auto-reload (development)")
@click.option("--force", "-f", is_flag=True, help="Force re-scan, ignoring any cached index (implies scan)")
def main(ctx: click.Context, host: str, port: int, reload: bool, force: bool) -> None:
    """Sourcebook — architecture-first development tool."""
    ctx.ensure_object(dict)
    ctx.obj["host"] = host
    ctx.obj["port"] = port
    ctx.obj["reload"] = reload
    if ctx.invoked_subcommand is None:
        if force:
            ctx.invoke(scan, force=force)
        else:
            ctx.invoke(serve)


@main.command()
@click.pass_context
def serve(ctx: click.Context) -> None:
    """Start the Sourcebook server and open the UI in a browser."""
    host = ctx.obj["host"]
    port = ctx.obj["port"]
    reload = ctx.obj["reload"]

    # Import settings here so db_path is resolved from CWD at run time
    from sourcebook.config import settings  # noqa: PLC0415

    url = f"http://{host}:{port}"
    click.echo(f"Sourcebook: project dir  {Path.cwd()}")
    click.echo(f"Sourcebook: database     {settings.db_path}")
    click.echo(f"Sourcebook: serving at   {url}")

    _open_browser(url)
    uvicorn.run("sourcebook.main:app", host=host, port=port, reload=reload)


@main.command()
@click.pass_context
@click.option("--force", "-f", is_flag=True, help="Force re-scan, ignoring any cached index")
def scan(ctx: click.Context, force: bool) -> None:
    """Scan the current directory and generate an architecture diagram."""
    asyncio.run(_do_scan(ctx, force=force))

    host = ctx.obj["host"]
    port = ctx.obj["port"]
    reload = ctx.obj["reload"]
    url = f"http://{host}:{port}"
    click.echo(f"Opening UI at {url}")
    _open_browser(url)
    uvicorn.run("sourcebook.main:app", host=host, port=port, reload=reload)


async def _do_scan(ctx: click.Context, force: bool = False) -> None:
    from sourcebook.ai_agent import stream_response  # noqa: PLC0415
    from sourcebook.config import settings  # noqa: PLC0415
    from sourcebook.database import get_diagram, init_db, save_diagram, set_project_name, snapshot_diagram  # noqa: PLC0415
    from sourcebook.scanner import build_condensed_summary, build_project_summary, load_from_cache, save_to_cache  # noqa: PLC0415
    from sourcebook.utils import parse_diagram_update  # noqa: PLC0415

    root = Path.cwd()
    cache_path = settings.index_path
    cached = None

    if not force:
        cached = load_from_cache(cache_path)
        if cached:
            click.echo(f"Using cached index ({cache_path})")
            click.echo("  Tip: pass --force / -f to run a fresh scan")

    await init_db()

    if cached is None:
        click.echo(f"Scanning {root} ...")
        full_summary = build_project_summary(root)
        condensed = build_condensed_summary(root)
        save_to_cache(condensed, cache_path)
        click.echo(f"Index saved → {cache_path}")
        summary_for_diagram = full_summary
    else:
        summary_for_diagram = cached

    click.echo(f"Detected type : {summary_for_diagram.project_type}")
    click.echo(f"Files found   : {summary_for_diagram.file_count}")

    history = [
        {
            "role": "user",
            "content": (
                "Analyse this codebase and generate a clean, grouped architecture diagram.\n\n"
                "Requirements:\n"
                "- Organise components into 3–6 logical groups (e.g. Frontend, Backend, Data, External, Infra)\n"
                "- Every node must have a group_id\n"
                "- Keep it concise: 8–20 nodes total, max 10–15 edges\n"
                "- Position groups with 300+ px gaps between centres so containers don't overlap\n"
                "- Within each group, space nodes 200 px apart\n"
                "- Emit only cross-group edges (skip intra-group edges unless critical)\n\n"
                + summary_for_diagram.text
            ),
        }
    ]

    full_response = ""
    click.echo("Generating diagram (this may take a moment) ...")
    with click.progressbar(length=100, label="AI scan") as bar:
        chunk_count = 0
        async for chunk in stream_response(history, diagram_context=None):
            full_response += chunk
            chunk_count += 1
            # Advance the bar cosmetically; cap at 99 until done
            if bar.pos < 99:
                bar.update(1)
        bar.update(100 - bar.pos)

    update = parse_diagram_update(full_response)
    if update and "nodes" in update:
        current_nodes, current_edges, current_groups = await get_diagram()
        if current_nodes:
            await snapshot_diagram(current_nodes, current_edges, "pre-scan snapshot", current_groups)
        await save_diagram(update["nodes"], update.get("edges", []), update.get("groups", []))
        await set_project_name(root.name)
        nodes, edges, groups = await get_diagram()
        click.echo(f"Diagram saved : {len(nodes)} nodes, {len(edges)} edges, {len(groups)} groups")
    else:
        click.echo("Warning: AI did not return a diagram update. Check the response.")
        click.echo(full_response[:500] if full_response else "(empty response)")
