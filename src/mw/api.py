from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from . import __version__, db, pipeline
from .impact import impact_score, impact_tier
from .config import Config, load_config

TAGS_METADATA = [
    {"name": "packages", "description": "Scored packages and signal evidence."},
    {"name": "alerts", "description": "Ad-hoc alerts and configured alert rules."},
    {"name": "system", "description": "Health and coverage."},
]


def _rows(rows) -> list[dict]:
    return [dict(r) for r in rows]


def _query_packages(
    conn,
    cfg: Config,
    system: str | None,
    band: str | None,
    min_score: float | None,
    min_dependents: int | None,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    where = ["s.model_version = ?"]
    args: list[object] = [cfg.model_version]
    if system:
        where.append("s.system = ?")
        args.append(system)
    if band:
        where.append("s.band = ?")
        args.append(band)
    if min_score is not None:
        where.append("s.score >= ?")
        args.append(min_score)
    if min_dependents is not None:
        where.append("i.dependent_count >= ?")
        args.append(min_dependents)
    where_sql = " AND ".join(where)
    from_sql = """FROM scores s
                  JOIN packages p ON p.system = s.system AND p.name = s.name
                  LEFT JOIN package_impact i
                    ON i.system = s.system AND i.name = s.name"""

    total = conn.execute(
        f"SELECT COUNT(*) {from_sql} WHERE {where_sql}", args
    ).fetchone()[0]
    rows = conn.execute(
        f"""SELECT s.system, s.name, s.score, s.band,
                   p.downloads_weekly, p.osv_count, p.fan_in,
                   p.fan_in_transitive, p.dependencies_count,
                   p.repo_url, p.license, i.dependent_count
            {from_sql}
            WHERE {where_sql}
            ORDER BY s.score DESC, s.name ASC
            LIMIT ? OFFSET ?""",
        args + [limit, offset],
    ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["impact_score"] = impact_score(
            item["dependent_count"], item["downloads_weekly"], item["fan_in_transitive"]
        )
        item["impact_tier"] = impact_tier(item["dependent_count"])
        items.append(item)
    return items, total


def _query_impact(
    conn,
    cfg: Config,
    system: str | None,
    min_dependents: int | None,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    where = ["s.model_version = ?"]
    args: list[object] = [cfg.model_version]
    if system:
        where.append("s.system = ?")
        args.append(system)
    if min_dependents is not None:
        where.append("i.dependent_count >= ?")
        args.append(min_dependents)
    where_sql = " AND ".join(where)
    rows = conn.execute(
        f"""SELECT s.system, s.name, s.score, s.band,
                   p.downloads_weekly, p.osv_count, p.fan_in,
                   p.fan_in_transitive, p.dependencies_count,
                   p.repo_url, p.license, i.dependent_count
            FROM scores s
            JOIN packages p ON p.system = s.system AND p.name = s.name
            LEFT JOIN package_impact i
              ON i.system = s.system AND i.name = s.name
            WHERE {where_sql}""",
        args,
    ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["impact_score"] = impact_score(
            item["dependent_count"], item["downloads_weekly"], item["fan_in_transitive"]
        )
        item["impact_tier"] = impact_tier(item["dependent_count"])
        items.append(item)
    items.sort(key=lambda item: (-item["impact_score"], -item["score"], item["name"]))
    total = len(items)
    return items[offset:offset + limit], total


def create_app(cfg: Config | None = None) -> FastAPI:
    cfg = cfg or load_config()
    app = FastAPI(
        title="MaintainerWatch",
        version=__version__,
        description="Open maintainer-level software supply-chain risk intelligence.",
        openapi_tags=TAGS_METADATA,
    )
    buckets: dict[str, deque] = defaultdict(deque)

    @app.middleware("http")
    async def auth_and_rate_limit(request: Request, call_next):
        path = request.url.path
        if path in {"/health", "/docs", "/openapi.json", "/redoc"}:
            return await call_next(request)

        api_key = os.environ.get(cfg.api.api_key_env)
        if api_key and request.headers.get("x-api-key") != api_key:
            return JSONResponse({"detail": "unauthorized"}, status_code=401)

        if cfg.api.rate_limit_rpm > 0:
            key = request.headers.get("x-api-key") or (
                request.client.host if request.client else "unknown"
            )
            now = time.monotonic()
            bucket = buckets[key]
            while bucket and now - bucket[0] >= 60:
                bucket.popleft()
            if len(bucket) >= cfg.api.rate_limit_rpm:
                return JSONResponse(
                    {"detail": "rate limit exceeded"},
                    status_code=429,
                    headers={"Retry-After": "60"},
                )
            bucket.append(now)

        return await call_next(request)

    def open_db():
        conn = db.connect(cfg.db_path)
        db.init_db(conn)
        return conn

    @app.get("/health", tags=["system"], summary="Health check")
    def health() -> dict:
        return {
            "status": "ok",
            "version": __version__,
            "model_version": cfg.model_version,
        }

    @app.get("/systems", tags=["system"], summary="Package counts per ecosystem")
    def systems() -> list[dict]:
        conn = open_db()
        try:
            return _rows(
                conn.execute(
                    """SELECT system, COUNT(*) AS packages
                       FROM packages GROUP BY system ORDER BY system"""
                ).fetchall()
            )
        finally:
            conn.close()

    @app.get("/packages", tags=["packages"], summary="List scored packages")
    def list_packages(
        response: Response,
        system: str | None = Query(
            None, description="Filter by ecosystem.", examples=["npm"]
        ),
        band: str | None = Query(
            None, description="Filter by risk band.", examples=["high"]
        ),
        min_score: float | None = Query(
            None, ge=0, le=100, description="Minimum score."
        ),
        min_dependents: int | None = Query(
            None, ge=0, description="Minimum deps.dev dependent count."
        ),
        limit: int = Query(50, ge=1, le=500, description="Page size."),
        offset: int = Query(0, ge=0, description="Number of rows to skip."),
    ) -> list[dict]:
        conn = open_db()
        try:
            items, total = _query_packages(
                conn, cfg, system, band, min_score, min_dependents, limit, offset
            )
        finally:
            conn.close()

        response.headers["X-Total-Count"] = str(total)
        response.headers["X-Limit"] = str(limit)
        response.headers["X-Offset"] = str(offset)
        next_offset = offset + limit
        response.headers["X-Next-Offset"] = (
            str(next_offset) if next_offset < total else ""
        )
        return items

    @app.get(
        "/packages/{system}/{name:path}",
        tags=["packages"],
        summary="Package score and evidence",
    )
    def package(system: str, name: str) -> dict:
        result = pipeline.scan(cfg, system, name)
        if result is None:
            raise HTTPException(status_code=404, detail="package not found")
        return result

    @app.get("/top", tags=["packages"], summary="Top risk packages")
    def top(
        response: Response,
        system: str | None = Query(None, description="Filter by ecosystem."),
        limit: int = Query(20, ge=1, le=500, description="Page size."),
        offset: int = Query(0, ge=0, description="Number of rows to skip."),
    ) -> list[dict]:
        return list_packages(
            response=response, system=system, band=None, min_score=None,
            min_dependents=None, limit=limit, offset=offset,
        )

    @app.get("/impact", tags=["packages"], summary="Top impact packages")
    def impact(
        response: Response,
        system: str | None = Query(None, description="Filter by ecosystem."),
        min_dependents: int | None = Query(
            None, ge=0, description="Minimum deps.dev dependent count."
        ),
        limit: int = Query(20, ge=1, le=500, description="Page size."),
        offset: int = Query(0, ge=0, description="Number of rows to skip."),
    ) -> list[dict]:
        conn = open_db()
        try:
            items, total = _query_impact(
                conn, cfg, system, min_dependents, limit, offset
            )
        finally:
            conn.close()
        response.headers["X-Total-Count"] = str(total)
        response.headers["X-Limit"] = str(limit)
        response.headers["X-Offset"] = str(offset)
        next_offset = offset + limit
        response.headers["X-Next-Offset"] = (
            str(next_offset) if next_offset < total else ""
        )
        return items

    @app.get("/alerts", tags=["alerts"], summary="Ad-hoc alert query")
    def alerts(
        min_score: float = Query(40.0, ge=0, le=100),
        signal: str | None = Query(None, examples=["publisher_change"]),
        min_signal: float = Query(0.5, ge=0, le=1),
        limit: int = Query(100, ge=1, le=500),
    ) -> list[dict]:
        return pipeline.alerts(
            cfg,
            min_score=min_score,
            signal=signal,
            min_signal=min_signal,
            limit=limit,
        )

    @app.get(
        "/alert-rules",
        tags=["alerts"],
        summary="Run configured alert rules without delivery",
    )
    def alert_rules() -> list[dict]:
        return pipeline.run_alert_rules(cfg, dry_run=True)

    return app
