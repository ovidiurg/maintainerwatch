from __future__ import annotations

from mw import db
from mw.models import IdentityLink
from mw.resolve import gpg, identity_map, store_links


class FakeClient:
    def __init__(self, text: str):
        self.text = text

    def get_text(self, url, headers=None, use_cache=True):
        return self.text


def test_gpg_lookup():
    text = (
        "info:1:1\n"
        "pub:ABCDEF0123456789:1:2048:1296691213::\n"
        "uid:Alice <alice@example.org>:1296691213::\n"
    )
    links = gpg.lookup(FakeClient(text), "npm", "pkg", "alice@example.org")
    assert len(links) == 1
    assert links[0].id_b == "gpg:abcdef0123456789"
    assert links[0].link_type == "gpg_key"
    assert links[0].confidence == "high"


def test_gpg_lookup_rejects_wrong_email():
    text = (
        "info:1:1\n"
        "pub:ABCDEF0123456789:1:2048:1296691213::\n"
        "uid:Bob <bob@example.org>:1296691213::\n"
    )
    assert gpg.lookup(FakeClient(text), "npm", "pkg", "alice@example.org") == []


def test_identity_map_unifies_shared_key():
    conn = db.connect(":memory:")
    db.init_db(conn)
    store_links(
        conn,
        [
            IdentityLink(
                system="npm", name="pkg", id_a="a@example.org",
                id_b="gpg:key1", link_type="gpg_key", confidence="high",
            ),
            IdentityLink(
                system="npm", name="pkg", id_a="b@example.org",
                id_b="gpg:key1", link_type="gpg_key", confidence="high",
            ),
            IdentityLink(
                system="npm", name="pkg", id_a="a@example.org",
                id_b="github:alice", link_type="email", confidence="high",
            ),
        ],
    )
    mapping = identity_map(conn, "npm", "pkg")
    assert mapping["a@example.org"] == mapping["b@example.org"]
    assert mapping["a@example.org"] == mapping["gpg:key1"]
    assert mapping["a@example.org"] == mapping["github:alice"]
    conn.close()
