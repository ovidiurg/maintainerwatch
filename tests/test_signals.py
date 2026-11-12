from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from mw import db
from mw.models import SignalEvidence
from mw.score import compute_score
from mw.signals import account_age, bus_factor, publisher_change, release_anomaly, signing_gap, typosquat
from mw.signals.base import Context


@pytest.fixture()
def conn():
    c = db.connect(":memory:")
    db.init_db(c)
    yield c
    c.close()


def _iso(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _add_package(conn, system="npm", name="pkg", downloads=0):
    conn.execute(
        "INSERT INTO packages (system, name, normalized, downloads_weekly) VALUES (?, ?, ?, ?)",
        (system, name, name.lower(), downloads),
    )


def _add_versions(conn, versions, system="npm", name="pkg"):
    for ver, published, publisher in versions:
        conn.execute(
            """INSERT INTO versions
                 (system, name, version, published_at, publisher_name, publisher_email,
                  has_sig, has_provenance, is_yanked)
               VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0)""",
            (system, name, ver, published, publisher, publisher),
        )


def _add_repo(conn, created_days_ago, share, contributors, system="npm", name="pkg"):
    conn.execute(
        """INSERT INTO repo_stats
             (system, name, repo_url, owner, owner_created_at,
              contributors_12m, top_author_share)
           VALUES (?, ?, 'https://github.com/o/r', 'o', ?, ?, ?)""",
        (system, name, _iso(created_days_ago), contributors, share),
    )


def test_typosquat_flags_close_name(conn):
    _add_package(conn, name="reqeusts", downloads=10)
    ctx = Context(conn=conn, system="npm", name="reqeusts",
                  downloads_weekly=10, top_names=["requests", "react"])
    ev = typosquat.compute(ctx)
    assert ev.value == 1.0
    assert ev.evidence["nearest"] == "requests"


def test_typosquat_ignores_existing_top_package(conn):
    _add_package(conn, name="requests", downloads=10_000_000)
    ctx = Context(conn=conn, system="npm", name="requests",
                  downloads_weekly=10_000_000, top_names=["requests"])
    ev = typosquat.compute(ctx)
    assert ev.value == 0.0


def test_release_anomaly_detects_dormancy(conn):
    _add_package(conn)
    _add_versions(conn, [("1.0.0", "2020-01-01T00:00:00+00:00", "a"),
                         ("1.0.1", "2020-02-01T00:00:00+00:00", "a"),
                         ("1.0.2", "2020-03-01T00:00:00+00:00", "a"),
                         ("2.0.0", "2023-01-01T00:00:00+00:00", "a")])
    ctx = Context(conn=conn, system="npm", name="pkg")
    ev = release_anomaly.compute(ctx)
    assert ev.applicable is True
    assert ev.evidence["dormancy"] == 1.0
    assert ev.value >= 0.8


def test_release_anomaly_not_applicable_with_few_versions(conn):
    _add_package(conn)
    _add_versions(conn, [("1.0.0", "2020-01-01T00:00:00+00:00", "a")])
    ev = release_anomaly.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is False


def test_signing_gap_npm_no_provenance(conn):
    _add_package(conn)
    _add_versions(conn, [("1.0.0", "2020-01-01T00:00:00+00:00", "a")])
    ev = signing_gap.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 1.0


def test_signing_gap_pypi_signed(conn):
    _add_package(conn, system="pypi")
    conn.execute(
        """INSERT INTO versions (system, name, version, published_at, has_sig)
           VALUES ('pypi', 'pkg', '1.0.0', '2020-01-01T00:00:00+00:00', 1)"""
    )
    ev = signing_gap.compute(Context(conn=conn, system="pypi", name="pkg"))
    assert ev.value == 0.0


def test_account_age_young(conn):
    _add_package(conn)
    _add_repo(conn, created_days_ago=30, share=0.5, contributors=5)
    ev = account_age.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 1.0


def test_account_age_old(conn):
    _add_package(conn)
    _add_repo(conn, created_days_ago=1500, share=0.5, contributors=5)
    ev = account_age.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 0.0


def test_bus_factor(conn):
    _add_package(conn)
    _add_repo(conn, created_days_ago=1000, share=0.9, contributors=3)
    ev = bus_factor.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 0.9


def test_publisher_change_recent(conn):
    _add_package(conn)
    _add_versions(conn, [("1.0.0", _iso(90), "alice@example.org"),
                         ("1.0.1", _iso(60), "alice@example.org"),
                         ("1.1.0", _iso(30), "bob@example.org")])
    ctx = Context(conn=conn, system="npm", name="pkg")
    ev = publisher_change.compute(ctx)
    assert ev.applicable is True
    assert ev.evidence["n_recent"] == 1
    assert ev.value == 0.5


def test_publisher_change_uses_identity_mapping(conn):
    _add_package(conn)
    _add_versions(conn, [("1.0.0", _iso(90), "alice@example.org"),
                         ("1.0.1", _iso(30), "alice@personal.org")])
    ctx = Context(conn=conn, system="npm", name="pkg",
                  identity_mapping={"alice@personal.org": "alice@example.org"})
    ev = publisher_change.compute(ctx)
    assert ev.evidence["n_recent"] == 0


def test_publisher_change_ignores_automation(conn):
    _add_package(conn)
    _add_versions(conn, [("1.0.0", _iso(90), "alice@example.org"),
                         ("1.0.1", _iso(60), "npm-oidc-no-reply@github.com"),
                         ("1.0.2", _iso(30), "alice@example.org")])
    ctx = Context(conn=conn, system="npm", name="pkg",
                  automation_identities=["npm-oidc-no-reply@github.com"],
                  automation_patterns=[r"\+oss-bot@"])
    ev = publisher_change.compute(ctx)
    assert ev.evidence["n_recent"] == 0
    assert ev.value == 0.0


def test_publisher_change_skips_bot_between_people(conn):
    _add_package(conn)
    _add_versions(conn, [("1.0.0", _iso(90), "alice@example.org"),
                         ("1.0.1", _iso(60), "npm-oidc-no-reply@github.com"),
                         ("1.0.2", _iso(30), "bob@example.org")])
    ctx = Context(conn=conn, system="npm", name="pkg",
                  automation_identities=["npm-oidc-no-reply@github.com"],
                  automation_patterns=[r"\+oss-bot@"])
    ev = publisher_change.compute(ctx)
    assert ev.evidence["n_recent"] == 1
    assert ev.value == 0.5


def test_score_is_reproducible():
    signals = {
        "publisher_change": SignalEvidence(value=0.5, evidence={"n_recent": 1}),
        "bus_factor": SignalEvidence(value=0.9, evidence={"share": 0.9}),
        "typosquat": SignalEvidence(value=0.0, evidence={"distance": 9}),
    }
    weights = {"publisher_change": 30, "bus_factor": 20, "typosquat": 10}
    a = compute_score(signals, weights, "0.1.0")
    b = compute_score(signals, weights, "0.1.0")
    assert a == b
    assert a[1] in {"low", "medium", "high"}


def test_score_ignores_not_applicable():
    signals = {
        "publisher_change": SignalEvidence(value=1.0, applicable=False, evidence={}),
        "typosquat": SignalEvidence(value=0.0, evidence={}),
    }
    score, band, _ = compute_score(signals, {"publisher_change": 30, "typosquat": 10}, "0.1.0")
    assert score == 0.0
    assert band == "low"
