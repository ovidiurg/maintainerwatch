from __future__ import annotations

import json

import pytest

from mw import db
from mw.signals import depsdev_findings
from mw.signals.base import Context


@pytest.fixture()
def conn():
    connection = db.connect(":memory:")
    db.init_db(connection)
    yield connection
    connection.close()


def _package(conn):
    conn.execute(
        "INSERT INTO packages (system, name, normalized) VALUES ('npm', 'pkg', 'pkg')"
    )


def _findings(conn, doc):
    db.upsert_findings(conn, [
        ("npm", "pkg", "1.0.0", json.dumps(doc), "2026-01-01"),
    ])


def test_depsdev_malicious_finding(conn):
    _package(conn)
    _findings(conn, {"packageFindings": [{"type": "MALICIOUS", "risk": "RISK_CRITICAL"}]})
    ev = depsdev_findings.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is True
    assert ev.value == 1.0


def test_depsdev_deprecated_finding(conn):
    _package(conn)
    _findings(conn, {"requestedVersion": {"findings": [{"type": "DEPRECATED"}]}})
    ev = depsdev_findings.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 0.4


def test_depsdev_no_findings(conn):
    _package(conn)
    _findings(conn, {"packageFindings": [], "requestedVersion": {"findings": []}})
    ev = depsdev_findings.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is False


def test_depsdev_vulnerable_and_low_usage(conn):
    _package(conn)
    _findings(conn, {"requestedVersion": {"findings": [{"type": "VULNERABLE"}]}})
    ev = depsdev_findings.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 0.5

    _findings(conn, {"packageFindings": [{"type": "LOW_USAGE"}]})
    ev = depsdev_findings.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 0.3


def test_depsdev_cooldown_and_invalid_payload(conn):
    _package(conn)
    _findings(conn, {"requestedVersion": {"findings": [{"type": "COOLDOWN"}]}})
    ev = depsdev_findings.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 0.2

    db.upsert_findings(conn, [("npm", "pkg", "1.0.0", "not-json", "2026-01-01")])
    ev = depsdev_findings.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is False


def test_depsdev_missing_data(conn):
    _package(conn)
    ev = depsdev_findings.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is False
