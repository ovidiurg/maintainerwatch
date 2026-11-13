from __future__ import annotations

from mw.ingest.gitlab import fetch_commits, fetch_repo_stats, parse_gitlab_repo


class FakeClient:
    def __init__(self, docs):
        self.docs = docs

    def get_json(self, url, headers=None, use_cache=True):
        return self.docs.get(url)


def test_parse_gitlab_repo():
    assert parse_gitlab_repo("https://gitlab.com/group/project") == "group/project"
    assert parse_gitlab_repo(
        "https://gitlab.com/group/subgroup/project.git"
    ) == "group/subgroup/project"
    assert parse_gitlab_repo("git@gitlab.com:group/project.git") == "group/project"
    assert parse_gitlab_repo(
        "https://gitlab.com/group/project/-/tree/main"
    ) == "group/project"
    assert parse_gitlab_repo("https://github.com/a/b") is None


def test_gitlab_repo_stats():
    api = "https://gitlab.com/api/v4"
    docs = {
        f"{api}/projects/group%2Fproject": {
            "id": 1,
            "web_url": "https://gitlab.com/group/project",
            "last_activity_at": "2024-01-01",
            "license": {"nickname": "MIT"},
            "namespace": {
                "id": 2, "kind": "group", "full_path": "group", "name": "Group",
            },
        },
        f"{api}/projects/1/repository/contributors?per_page=100": [
            {"commits": 8}, {"commits": 2},
        ],
        f"{api}/groups/2": {"created_at": "2015-01-01"},
    }
    stats = fetch_repo_stats(
        FakeClient(docs), "npm", "pkg", "https://gitlab.com/group/project", None
    )
    assert stats is not None
    assert stats.owner == "group"
    assert stats.top_author_share == 0.8
    assert stats.contributors_12m == 2
    assert stats.license == "MIT"
    assert stats.owner_created_at == "2015-01-01"


def test_gitlab_commits():
    api = "https://gitlab.com/api/v4"
    docs = {
        f"{api}/projects/group%2Fproject": {"id": 1},
        f"{api}/projects/1/repository/commits?per_page=100&page=1": [
            {
                "id": "abc",
                "created_at": "2024-01-01T00:00:00Z",
                "author_name": "Alice",
                "author_email": "alice@example.org",
            }
        ],
    }
    commits = fetch_commits(
        FakeClient(docs), "https://gitlab.com/group/project", None, pages=1
    )
    assert commits[0]["sha"] == "abc"
    assert commits[0]["author_login"] == "alice@example.org"
    assert commits[0]["author_email"] == "alice@example.org"
