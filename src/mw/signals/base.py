from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import median

from .. import db


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        s = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def days_between(a: datetime, b: datetime) -> float:
    return abs((b - a).total_seconds()) / 86400.0


def days_since(value: str | None, *, now: datetime | None = None) -> float | None:
    dt = parse_ts(value)
    if not dt:
        return None
    return max(0.0, days_between(dt, now or now_utc()))


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def piecewise(value: float, points: list[tuple[float, float]]) -> float:
    for threshold, result in points:
        if value < threshold:
            return result
    return points[-1][1] if points else 0.0


def median_absolute_deviation(values: list[float]) -> float:
    if not values:
        return 0.0
    med = median(values)
    return median([abs(v - med) for v in values]) or 0.0


@dataclass
class Context:
    conn: sqlite3.Connection
    system: str
    name: str
    downloads_weekly: int = 0
    top_names: list[str] = field(default_factory=list)
    identity_mapping: dict[str, str] = field(default_factory=dict)
    as_of: str | None = None
    automation_identities: list[str] = field(default_factory=list)
    automation_patterns: list[str] = field(default_factory=list)

    @property
    def versions(self) -> list[sqlite3.Row]:
        rows = db.get_versions(self.conn, self.system, self.name)
        if not self.as_of:
            return rows
        cutoff = parse_ts(self.as_of)
        if not cutoff:
            return rows
        out = []
        for r in rows:
            dt = parse_ts(r["published_at"])
            if dt is not None and dt < cutoff:
                out.append(r)
        return out

    @property
    def repo(self) -> sqlite3.Row | None:
        return db.get_repo_stats(self.conn, self.system, self.name)
