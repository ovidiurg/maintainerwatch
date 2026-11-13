from __future__ import annotations

from mw import db
from mw.snapshots import import_snapshot_records, parse_metadata_identities


def test_parse_metadata_identities():
    text = """Metadata-Version: 2.1
Name: demo
Author: Alice Example
Author-email: Alice Example <alice@example.org>
Maintainer: Bob
Maintainer-email: bob@example.org

Description text that should be ignored.
"""
    identities = parse_metadata_identities(text)
    assert "alice@example.org" in identities
    assert "Alice Example" in identities
    assert "bob@example.org" in identities
    assert "Bob" in identities


def test_import_snapshot_records():
    conn = db.connect(":memory:")
    db.init_db(conn)
    count = import_snapshot_records(
        conn,
        [
            {
                "system": "pypi",
                "name": "demo",
                "captured_at": "2024-01-01T00:00:00+00:00",
                "maintainers": ["alice", "alice@example.org"],
            }
        ],
    )
    assert count == 1
    row = conn.execute(
        "SELECT * FROM snapshots WHERE system='pypi' AND name='demo'"
    ).fetchone()
    assert row is not None
    assert "alice@example.org" in row["maintainer_set_json"]
    conn.close()
