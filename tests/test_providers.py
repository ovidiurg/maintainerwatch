from __future__ import annotations

import json

from mw import db, providers
from mw.models import Package, RepoStats, Version


def test_provider_context_confirms_advisory_and_findings(tmp_path):
    conn = db.connect(tmp_path / "providers.sqlite")
    db.init_db(conn)
    db.upsert_packages(conn, [Package(system="npm", name="pkg")])
    db.upsert_versions(conn, [
        Version(system="npm", name="pkg", version="1.0.0", published_at="2026-01-01T00:00:00Z"),
    ])
    db.upsert_osv(conn, [(
        "npm", "pkg", "MAL-2026-1", "high", "2026-01-02T00:00:00Z",
        json.dumps([{"package": {"ecosystem": "npm", "name": "pkg"}, "versions": ["1.0.0"]}]),
        "malicious", None,
    )])
    db.upsert_findings(conn, [(
        "npm", "pkg", "1.0.0",
        json.dumps({"requestedVersion": {"findings": [{"type": "MALICIOUS", "risk": "RISK_HIGH"}]}}),
        "2026-01-03",
    )])
    db.upsert_repo_stats(conn, [RepoStats(system="npm", name="pkg", scorecard_score=3.0)])
    conn.commit()

    result = providers.build_context(conn, "npm", "pkg")
    assert result is not None
    assert result["current_version"] == "1.0.0"
    assert result["osv"]["status"] == "affected"
    assert result["depsdev"]["status"] == "findings"
    assert result["scorecard"]["status"] == "available"
    assert result["consensus"]["advisory"] == "confirmed"
    assert result["consensus"]["providers_available"] == 3
    conn.close()


def test_provider_context_without_data_is_none(tmp_path):
    conn = db.connect(tmp_path / "providers-empty.sqlite")
    db.init_db(conn)
    db.upsert_packages(conn, [Package(system="npm", name="pkg")])
    conn.commit()
    result = providers.build_context(conn, "npm", "pkg")
    assert result is not None
    assert result["osv"]["status"] == "none"
    assert result["depsdev"]["status"] == "unavailable"
    assert result["consensus"]["advisory"] == "none"
    conn.close()
