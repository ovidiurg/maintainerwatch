from __future__ import annotations

import json
from typing import Optional

import typer

from . import db, pipeline
from .config import load_config
from .export import export_dataset
from .report import build_report

app = typer.Typer(
    help="MaintainerWatch: open maintainer-level supply-chain risk intelligence.",
    no_args_is_help=True,
)


@app.command()
def init(config: Optional[str] = typer.Option(None, help="Config file path.")) -> None:
    """Create the SQLite schema."""
    cfg = load_config(config)
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    conn.close()
    typer.echo(f"initialised {cfg.db_path}")


@app.command()
def ingest(
    system: Optional[str] = typer.Option(None, help="npm or pypi (default: all)."),
    top: Optional[int] = typer.Option(None, help="Number of top packages."),
    seed_file: Optional[str] = typer.Option(None, help="Newline-separated package list."),
    github: bool = typer.Option(True, help="Fetch GitHub repo stats."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """Ingest public registry metadata."""
    cfg = load_config(config)
    systems = [system] if system else cfg.ecosystems
    for name in systems:
        result = pipeline.ingest_system(
            cfg, name, top_n=top, seed_file=seed_file, with_github=github
        )
        typer.echo(json.dumps(result))


@app.command()
def resolve(
    limit: Optional[int] = typer.Option(None, help="Resolve only the first N packages."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """Resolve maintainer identities (Keybase, GitHub email/GPG, provenance)."""
    cfg = load_config(config)
    typer.echo(json.dumps(pipeline.resolve_all(cfg, limit=limit)))


@app.command("score-all")
def score_all(config: Optional[str] = typer.Option(None, help="Config file path.")) -> None:
    """Compute signals and scores for every ingested package."""
    cfg = load_config(config)
    typer.echo(json.dumps(pipeline.score_all(cfg)))


@app.command()
def scan(
    name: str = typer.Argument(..., help="Package name."),
    system: str = typer.Option("npm", "--system", "-s", help="npm or pypi."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """Print the score and evidence for one package."""
    cfg = load_config(config)
    result = pipeline.scan(cfg, system, name)
    if not result:
        typer.echo(f"no score for {system}/{name}", err=True)
        raise typer.Exit(code=1)
    typer.echo(json.dumps(result, indent=2))


@app.command("export")
def export_cmd(
    format: str = typer.Option("parquet", help="parquet or csv."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """Export the scored dataset."""
    cfg = load_config(config)
    path, n = export_dataset(cfg, fmt=format)
    typer.echo(json.dumps({"path": str(path), "records": n}))


@app.command()
def report(
    out: str = typer.Option("report.html", help="Output HTML path."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """Build a static HTML report."""
    cfg = load_config(config)
    path, n = build_report(cfg, out=out)
    typer.echo(json.dumps({"path": str(path), "records": n}))


if __name__ == "__main__":
    app()
