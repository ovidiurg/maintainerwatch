from __future__ import annotations

from mw.lookup import diff_indexes, format_diff_markdown

OLD = {
    "model_version": "0.5.3",
    "generated_at": "2026-11-16T00:00:00+00:00",
    "packages": {
        "npm:a": {"system": "npm", "name": "a", "score": 10.0, "band": "low"},
        "npm:b": {"system": "npm", "name": "b", "score": 55.0, "band": "high"},
    },
}
NEW = {
    "model_version": "0.5.3",
    "generated_at": "2026-11-23T00:00:00+00:00",
    "packages": {
        "npm:a": {"system": "npm", "name": "a", "score": 30.0, "band": "medium"},
        "npm:c": {"system": "npm", "name": "c", "score": 60.0, "band": "high"},
    },
}


def test_diff_indexes_reports_new_resolved_and_changed():
    diff = diff_indexes(OLD, NEW)
    assert [item["name"] for item in diff["added_high_medium"]] == ["c"]
    assert [item["name"] for item in diff["resolved_high_medium"]] == ["b"]
    assert diff["changed"][0]["old"]["name"] == "a"
    markdown = format_diff_markdown(diff)
    assert "New high/medium: 1" in markdown
    assert "Resolved high/medium: 1" in markdown
    assert "npm/a" in markdown
