from __future__ import annotations

from mw.evaluate import metrics_at, replay_score
from mw.ingest.github import detect_license_text
from mw.ingest.github_repo import fetch_package as fetch_github_package
from mw.models import SignalEvidence


def test_replay_score_renormalises_over_applicable_signals():
    signals = {
        "publisher_change": SignalEvidence(value=0.5, applicable=True),
        "release_anomaly": SignalEvidence(value=0.0, applicable=False),
        "signing_gap": SignalEvidence(value=1.0, applicable=True),
    }
    weights = {"publisher_change": 30, "release_anomaly": 15, "signing_gap": 10}
    assert replay_score(signals, weights) == 62.5


def test_replay_score_without_applicable_signals():
    signals = {
        "publisher_change": SignalEvidence(value=1.0, applicable=False),
    }
    assert replay_score(signals, {"publisher_change": 30}) == 0.0


def test_metrics_at():
    metrics = metrics_at([50, 0, 40], [10, 20, 45], 40)
    assert metrics["tp"] == 2
    assert metrics["fn"] == 1
    assert metrics["fp"] == 1
    assert metrics["tn"] == 2
    assert metrics["precision"] == 0.667
    assert metrics["recall"] == 0.667
    assert metrics["false_positive_rate"] == 0.333


class FakeClient:
    def __init__(self, docs):
        self.docs = docs

    def get_json(self, url, headers=None, use_cache=True):
        return self.docs.get(url)


def test_github_repo_release_versions():
    api = "https://api.github.com"
    docs = {
        f"{api}/repos/o/r": {
            "html_url": "https://github.com/o/r",
            "created_at": "2020-01-01T00:00:00Z",
            "license": {"spdx_id": "MIT"},
            "owner": {"login": "o"},
        },
        f"{api}/repos/o/r/releases?per_page=100": [
            {"tag_name": "v1.0.0", "published_at": "2024-01-01T00:00:00Z",
             "author": {"login": "alice"}},
            {"tag_name": "v1.1.0", "published_at": "2024-02-01T00:00:00Z",
             "author": {"login": "bob"}},
        ],
    }
    result = fetch_github_package(FakeClient(docs), "o/r", token="test")
    assert result is not None
    package, versions, maintainers = result
    assert package.repo_url == "https://github.com/o/r"
    assert [v.version for v in versions] == ["v1.0.0", "v1.1.0"]
    assert versions[1].publisher_name == "bob"
    assert {m.identity for m in maintainers} == {"o", "alice", "bob"}


def test_github_noassertion_license_fallback():
    import base64

    api = "https://api.github.com"
    gpl = "GNU GENERAL PUBLIC LICENSE\nVersion 2, June 1991\n"
    docs = {
        f"{api}/repos/o/r": {
            "html_url": "https://github.com/o/r",
            "created_at": "2020-01-01T00:00:00Z",
            "license": {"spdx_id": "NOASSERTION"},
            "owner": {"login": "o"},
        },
        f"{api}/repos/o/r/releases?per_page=100": [],
        f"{api}/repos/o/r/tags?per_page=100": [{"name": "v1.0.0"}],
        f"{api}/repos/o/r/license": {
            "content": base64.b64encode(gpl.encode()).decode(),
        },
    }
    result = fetch_github_package(FakeClient(docs), "o/r", token="test")
    assert result is not None
    package, _, _ = result
    assert package.license == "GPL-2.0"
    assert detect_license_text(gpl) == "GPL-2.0"
