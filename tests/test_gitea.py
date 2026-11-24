from __future__ import annotations

from mw.ingest.gitea import fetch_commits, fetch_repo_stats, parse_gitea_repo


class FakeClient:
    def __init__(self, docs):
        self.docs = docs
    def get_json(self, url, headers=None, use_cache=True):
        return self.docs.get(url)


def test_parse_gitea_repo():
    assert parse_gitea_repo("https://codeberg.org/zesterer/spin") == ("codeberg.org", "zesterer/spin")
    assert parse_gitea_repo("https://code.haverbeke.berlin/codemirror/view") == (
        "code.haverbeke.berlin", "codemirror/view"
    )
    assert parse_gitea_repo("https://gitlab.com/a/b") is None


def test_gitea_repo_stats_and_commits():
    repo = "https://codeberg.org/api/v1/repos/zesterer/spin"
    docs = {
        repo: {
            "html_url": "https://codeberg.org/zesterer/spin",
            "owner": {"login": "zesterer", "created": "2025-11-28T00:45:09+01:00"},
            "updated_at": "2026-08-17T22:01:10+02:00",
            "archived": False, "stars_count": 5, "forks_count": 2, "open_issues_count": 11,
        },
        repo + "/commits?limit=100": [
            {"sha": "a", "commit": {"author": {"name": "Alice", "email": "a@example.org"}}},
            {"sha": "b", "commit": {"author": {"name": "Bob", "email": "b@example.org"}}},
        ],
        repo + "/commits?limit=50&page=1": [
            {"sha": "a", "created": "2026-01-01", "commit": {"author": {"name": "Alice", "email": "a@example.org", "date": "2026-01-01"}}},
        ],
    }
    stats = fetch_repo_stats(FakeClient(docs), "crates", "spin", "https://codeberg.org/zesterer/spin", None)
    assert stats is not None
    assert stats.owner == "zesterer"
    assert stats.contributors_12m == 2
    assert stats.top_author_share == 0.5
    commits = fetch_commits(FakeClient(docs), "https://codeberg.org/zesterer/spin", None, pages=1)
    assert commits[0]["sha"] == "a"
