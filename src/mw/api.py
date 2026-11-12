from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from . import db, pipeline
from .config import Config, load_config


def _rows(rows) -> list[dict]:
    return [dict(r) for r in rows]


def create_app(cfg: Config | None = None) -> FastAPI:
    cfg = cfg or load_config()
    app = FastAPI(
        title="MaintainerWatch",
        version="0.2.0",
        description="Open maintainer-level software supply-chain risk intelligence.",
    )

    def open_db():
        conn = db.connect(cfg.db_path)
        db.init_db(conn)
        return conn

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "model_version": cfg.model_version}

    @app.get("/systems")
    def systems() -> list[dict]:
        conn = open_db()
        try:
            rows = conn.execute(
                """SELECT system, COUNT(*) AS packages
                   FROM packages GROUP BY system ORDER BY system"""
            ).fetchall()
            return _rows(rows)
        finally:
            conn.close()

    @app.get("/packages")
    def list_packages(
        system: str | None = Query(None),
        band: str | None = Query(None),
        min_score: float | None = Query(None),
        limit: int = Query(50, ge=1, le=500),
    ) -> list[dict]:
        sql = """SELECT s.system, s.name, s.score, s.band,
                        p.downloads_weekly, p.osv_count, p.fan_in,
                        p.fan_in_transitive, p.dependencies_count,
                        p.repo_url, p.license
                 FROM scores s
                 JOIN packages p ON p.system = s.system AND p.name = s.name
                 WHERE s.model_version = ?"""
        args: list[object] = [cfg.model_version]
        if system:
            sql += " AND s.system = ?"
            args.append(system)
        if band:
            sql += " AND s.band = ?"
            args.append(band)
        if min_score is not None:
            sql += " AND s.score >= ?"
            args.append(min_score)
        sql += " ORDER BY s.score DESC, s.name ASC LIMIT ?"
        args.append(limit)

        conn = open_db()
        try:
            return _rows(conn.execute(sql, args).fetchall())
        finally:
            conn.close()

    @app.get("/packages/{system}/{name}")
    def package(system: str, name: str) -> dict:
        result = pipeline.scan(cfg, system, name)
        if result is None:
            raise HTTPException(status_code=404, detail="package not found")
        return result

    @app.get("/top")
    def top(
        system: str | None = Query(None),
        limit: int = Query(20, ge=1, le=500),
    ) -> list[dict]:
        return list_packages(system=system, band=None, min_score=None, limit=limit)

    @app.get("/alerts")
    def alerts(
        min_score: float = Query(40.0),
        signal: str | None = Query(None),
        min_signal: float = Query(0.5),
        limit: int = Query(100, ge=1, le=500),
    ) -> list[dict]:
        return pipeline.alerts(
            cfg,
            min_score=min_score,
            signal=signal,
            min_signal=min_signal,
            limit=limit,
        )

    return app
