from __future__ import annotations

import json

import pytest

from mw import db
from mw.osv_match import affected
from mw.signals import osv_risk
from mw.signals.base import Context


@pytest.fixture()
def conn():
    connection = db.connect(":memory:")
    db.init_db(connection)
    yield connection
    connection.close()


def _package(conn, name="pkg", version="4.17.20"):
    conn.execute(
        "INSERT INTO packages (system, name, normalized) VALUES ('npm', ?, ?)",
        (name, name),
    )
    conn.execute(
        "INSERT INTO versions (system, name, version, published_at) "
        "VALUES ('npm', ?, ?, '2024-01-01T00:00:00+00:00')",
        (name, version),
    )


def _affected(ranges):
    return json.dumps([{
        "package": {"name": "pkg", "ecosystem": "npm"},
        "ranges": [{"type": "SEMVER", "events": ranges}],
    }])


def test_osv_range_fixed_boundary():
    data = _affected([{"introduced": "0"}, {"fixed": "4.17.21"}])
    assert affected(data, "npm", "pkg", "4.17.20") is True
    assert affected(data, "npm", "pkg", "4.17.21") is False


def test_osv_range_last_affected():
    data = _affected([{"introduced": "1.0.0"}, {"last_affected": "1.2.0"}])
    assert affected(data, "npm", "pkg", "1.1.0") is True
    assert affected(data, "npm", "pkg", "1.2.1") is False


def test_osv_explicit_versions():
    data = json.dumps([{
        "package": {"name": "pkg", "ecosystem": "npm"},
        "versions": ["1.0.0", "1.0.1"],
    }])
    assert affected(data, "npm", "pkg", "1.0.1") is True
    assert affected(data, "npm", "pkg", "1.0.2") is False


def test_osv_signal_only_for_current_version(conn):
    _package(conn, version="4.17.20")
    db.upsert_osv(conn, [(
        "npm", "pkg", "MAL-2025-1", None, None,
        _affected([{"introduced": "0"}, {"fixed": "4.17.21"}]),
        "malicious version", None,
    )])
    ev = osv_risk.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is True
    assert ev.value == 1.0

    conn.execute("UPDATE versions SET version='4.17.21' WHERE name='pkg'")
    ev = osv_risk.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is False


def test_osv_signal_cve_is_moderate(conn):
    _package(conn)
    db.upsert_osv(conn, [(
        "npm", "pkg", "GHSA-test", None, None,
        _affected([{"introduced": "0"}]),
        "vulnerability", None,
    )])
    ev = osv_risk.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 0.5


def test_osv_mismatch_and_invalid_payload():
    assert affected("not-json", "npm", "pkg", "1.0.0") is False
    assert affected(_affected([{"introduced": "0"}]), "pypi", "other", "1.0.0") is False
    assert affected(_affected([{"introduced": "2.0.0"}]), "npm", "pkg", "1.0.0") is False
