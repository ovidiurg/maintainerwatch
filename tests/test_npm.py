from __future__ import annotations

from mw.ingest.npm import parse_repo_url


def test_parse_repo_url_supports_shorthand_and_ssh():
    assert parse_repo_url("github:subquery/subql") == "https://github.com/subquery/subql"
    assert parse_repo_url("gitlab:group/project") == "https://gitlab.com/group/project"
    assert parse_repo_url("git+ssh://git@github.com/o/r.git") == "https://github.com/o/r"
    assert parse_repo_url("ssh://git@github.com/o/r") == "https://github.com/o/r"
    assert parse_repo_url("git@github.com:o/r.git") == "https://github.com/o/r"
    assert parse_repo_url("git+https://github.com/o/r.git") == "https://github.com/o/r"
