from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from . import db, pipeline, validation
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
    system: Optional[str] = typer.Option(
        None, help="npm, pypi, crates, maven or github (default: all)."
    ),
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
def maintain(
    with_commits: bool = typer.Option(True, help="Refresh GitHub/GitLab commits."),
    limit: Optional[int] = typer.Option(None, help="Limit packages per backfill."),
    export: bool = typer.Option(True, help="Export datasets and build the report."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """Run the recurring post-ingest pipeline (cron-friendly)."""
    cfg = load_config(config)
    typer.echo(json.dumps(
        pipeline.maintain(
            cfg, with_commits=with_commits, limit=limit, export=export
        ),
        indent=2,
    ))


@app.command()
def snapshot(
    system: Optional[str] = typer.Option(None, help="Limit to one ecosystem."),
    limit: Optional[int] = typer.Option(None, help="Limit packages."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """Record a maintainer snapshot for the current database state."""
    cfg = load_config(config)
    typer.echo(json.dumps(
        pipeline.record_current_snapshots(cfg, system=system, limit=limit)
    ))


@app.command("evaluate-validation")
def evaluate_validation(
    dataset: str = typer.Option("validation/v1", help="Validation dataset directory."),
    max_positives: Optional[int] = typer.Option(None, help="Limit positives."),
    max_controls: Optional[int] = typer.Option(None, help="Limit controls."),
    since: Optional[str] = typer.Option(None, help="Only positives at/after this ISO date."),
    until: Optional[str] = typer.Option(None, help="Only positives at/before this ISO date."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """Evaluate the current model on the validation dataset."""
    cfg = load_config(config)
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    result = validation.evaluate(
        conn, cfg, dataset,
        max_positives=max_positives, max_controls=max_controls,
        since=since, until=until,
    )
    conn.close()
    typer.echo(json.dumps({
        "coverage": result["coverage"],
        "metrics": result["metrics"],
    }, indent=2))


@app.command("prioritize-impact")
def prioritize_impact_cmd(
    system: Optional[str] = typer.Option(None, help="Only this ecosystem."),
    limit: int = typer.Option(50, help="Ranked packages to print."),
    missing_deps_limit: int = typer.Option(200, help="Missing dependency seeds to write."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """Rank packages by dependents, downloads and transitive fan-in."""
    cfg = load_config(config)
    typer.echo(json.dumps(
        pipeline.prioritize_impact(cfg, system, limit, missing_deps_limit),
        indent=2,
    ))


@app.command("enrich-findings")
def enrich_findings_cmd(
    system: Optional[str] = typer.Option(None, help="Only this ecosystem."),
    limit: int = typer.Option(500, help="Maximum packages to enrich."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """Fetch deps.dev findings for high-download packages."""
    cfg = load_config(config)
    typer.echo(json.dumps(pipeline.enrich_findings(cfg, system, limit)))


@app.command("enrich-scorecard")
def enrich_scorecard_cmd(
    system: Optional[str] = typer.Option(None, help="Only this ecosystem."),
    limit: int = typer.Option(500, help="Maximum repositories to enrich."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """Fetch individual OpenSSF Scorecard checks for existing repos."""
    cfg = load_config(config)
    typer.echo(json.dumps(pipeline.enrich_scorecard(cfg, system, limit)))


@app.command("enrich-impact")
def enrich_impact_cmd(
    system: Optional[str] = typer.Option(None, help="Only this ecosystem."),
    limit: int = typer.Option(500, help="Maximum packages to enrich."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """Fetch deps.dev dependent counts for high-download packages."""
    cfg = load_config(config)
    typer.echo(json.dumps(pipeline.enrich_impact(cfg, system, limit)))


@app.command("enrich-github")
def enrich_github_cmd(
    system: Optional[str] = typer.Option(None, help="Only this ecosystem."),
    limit: int = typer.Option(100, help="Maximum packages to enrich."),
    pages: int = typer.Option(2, help="GitHub commit pages per repository."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """Fetch repo stats, Scorecard and recent commits for selected packages."""
    cfg = load_config(config)
    typer.echo(json.dumps(pipeline.enrich_github(cfg, system, limit, pages)))


@app.command("backfill-osv")
def backfill_osv_cmd(
    system: Optional[str] = typer.Option(None, help="Only this ecosystem."),
    limit: int = typer.Option(500, help="Maximum advisories to fetch."),
    malicious_only: bool = typer.Option(False, help="Only MAL- advisories."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """Fetch affected-version ranges for stored OSV advisories."""
    cfg = load_config(config)
    typer.echo(json.dumps(
        pipeline.backfill_osv(cfg, system, limit, malicious_only)
    ))


@app.command("backfill-deps")
def backfill_deps(
    system: Optional[str] = typer.Option(None, help="npm, pypi, crates or maven."),
    limit: Optional[int] = typer.Option(None, help="Limit packages."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """Backfill dependency edges and fan-in for ingested packages."""
    cfg = load_config(config)
    typer.echo(json.dumps(pipeline.backfill_dependencies(cfg, system=system, limit=limit)))


@app.command("backfill-licenses")
def backfill_licenses(
    system: Optional[str] = typer.Option(None, help="npm, pypi, crates, maven or github."),
    limit: Optional[int] = typer.Option(None, help="Limit packages."),
    refresh: bool = typer.Option(False, help="Bypass the HTTP cache for repo licenses."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """Backfill license classifiers and repository licenses."""
    cfg = load_config(config)
    typer.echo(json.dumps(
        pipeline.backfill_licenses(
            cfg, system=system, limit=limit, refresh=refresh
        )
    ))


@app.command("backfill-commits")
def backfill_commits(
    system: Optional[str] = typer.Option(None, help="npm, pypi, crates, maven or github."),
    name: Optional[str] = typer.Option(None, help="Only this package name."),
    until: Optional[str] = typer.Option(None, help="Fetch commits before this ISO date."),
    pages: int = typer.Option(2, help="GitHub commit pages (100 per page)."),
    limit: Optional[int] = typer.Option(None, help="Limit packages."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """Backfill recent GitHub commits for commit-level signals."""
    cfg = load_config(config)
    typer.echo(json.dumps(
        pipeline.backfill_commits(
            cfg, system=system, name=name, until=until,
            pages=pages, limit=limit,
        )
    ))


@app.command("backfill-snapshots")
def backfill_snapshots(
    source: Optional[str] = typer.Option(None, help="JSONL, JSON or CSV snapshot file."),
    limit: Optional[int] = typer.Option(None, help="Limit PyPI packages."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """Import or reconstruct historical maintainer snapshots."""
    cfg = load_config(config)
    typer.echo(json.dumps(
        pipeline.backfill_snapshots(cfg, source=source, limit=limit)
    ))


@app.command("delete-package")
def delete_package_cmd(
    system: str = typer.Option(..., help="npm, pypi, crates, maven or github."),
    name: str = typer.Option(..., help="Package name."),
    yes: bool = typer.Option(False, "--yes", help="Actually delete; otherwise dry-run."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """Remove a package and its records/links for privacy or correction requests."""
    cfg = load_config(config)
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    tables = (
        "versions", "maintainers", "repo_stats", "osv", "signals",
        "scores", "snapshots", "identity_links", "dependencies",
        "commits", "package_impact", "packages",
    )
    if not yes:
        counts = {
            table: conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE system=? AND name=?",
                (system, name),
            ).fetchone()[0]
            for table in tables
        }
        conn.close()
        typer.echo(json.dumps({"dry_run": True, "system": system, "name": name, **counts}))
        return
    counts = db.delete_package(conn, system, name)
    conn.close()
    typer.echo(json.dumps({"deleted": True, "system": system, "name": name, **counts}))


@app.command()
def scan(
    name: str = typer.Argument(..., help="Package name."),
    system: str = typer.Option(
        "npm", "--system", "-s", help="npm, pypi, crates, maven or github."
    ),
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
    format: str = typer.Option(
        "parquet", help="parquet, csv, json, spdx, cyclonedx or osv."
    ),
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


@app.command()
def alerts(
    min_score: float = typer.Option(40.0, help="Minimum score."),
    signal: Optional[str] = typer.Option(None, help="Require this signal."),
    min_signal: float = typer.Option(0.5, help="Minimum signal value."),
    limit: int = typer.Option(100, help="Maximum number of alerts."),
    rules: bool = typer.Option(False, help="Run the alert rules from config."),
    webhook: Optional[str] = typer.Option(None, help="Webhook URL override."),
    email: Optional[str] = typer.Option(None, help="Email recipient override."),
    dry_run: bool = typer.Option(False, help="Match rules without delivering."),
    out: Optional[str] = typer.Option(None, help="Write JSON to this path."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """List packages above a score, or run configured alert rules."""
    cfg = load_config(config)
    if rules:
        result = pipeline.run_alert_rules(
            cfg, out=out, webhook=webhook, email=email, dry_run=dry_run
        )
        summary = [
            {
                "rule": item["rule"],
                "count": item["count"],
                "webhook": item.get("webhook"),
                "email": item.get("email"),
            }
            for item in result
        ]
        typer.echo(json.dumps(summary, indent=2))
        return

    result = pipeline.alerts(
        cfg, min_score=min_score, signal=signal,
        min_signal=min_signal, limit=limit,
    )
    payload = json.dumps(result, indent=2)
    if out:
        Path(out).write_text(payload, encoding="utf-8")
        typer.echo(json.dumps({"path": out, "alerts": len(result)}))
    else:
        typer.echo(payload)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind address."),
    port: int = typer.Option(8000, help="Bind port."),
    config: Optional[str] = typer.Option(None, help="Config file path."),
) -> None:
    """Run the read-only REST API."""
    cfg = load_config(config)
    try:
        import uvicorn
    except ImportError:
        typer.echo("uvicorn is required: pip install fastapi uvicorn", err=True)
        raise typer.Exit(code=1)
    from .api import create_app

    uvicorn.run(create_app(cfg), host=host, port=port)


if __name__ == "__main__":
    app()
