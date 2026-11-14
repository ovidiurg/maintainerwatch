from __future__ import annotations

import pytest

from mw import db


@pytest.fixture()
def conn():
    connection = db.connect(":memory:")
    db.init_db(connection)
    yield connection
    connection.close()


def test_delete_package_removes_records_and_inbound_dependencies(conn):
    conn.execute(
        "INSERT INTO packages (system, name, normalized) VALUES ('npm', 'pkg', 'pkg')"
    )
    conn.execute(
        "INSERT INTO versions (system, name, version) VALUES ('npm', 'pkg', '1.0.0')"
    )
    conn.execute(
        "INSERT INTO maintainers (system, name, identity, source) "
        "VALUES ('npm', 'pkg', 'alice', 'npm')"
    )
    conn.execute(
        "INSERT INTO identity_links (system, name, id_a, id_b, link_type, confidence) "
        "VALUES ('npm', 'pkg', 'alice', 'alice@example.org', 'email', 'high')"
    )
    conn.execute(
        "INSERT INTO dependencies (system, name, version, dep_system, dep_name) "
        "VALUES ('npm', 'pkg', '1.0.0', 'npm', 'dep')"
    )
    conn.execute(
        "INSERT INTO dependencies (system, name, version, dep_system, dep_name) "
        "VALUES ('npm', 'other', '1.0.0', 'npm', 'pkg')"
    )
    conn.commit()

    counts = db.delete_package(conn, "npm", "pkg")

    assert counts["packages"] == 1
    assert counts["versions"] == 1
    assert counts["identity_links"] == 1
    assert counts["inbound_dependencies"] == 1
    assert conn.execute("SELECT COUNT(*) FROM packages").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM dependencies").fetchone()[0] == 0
