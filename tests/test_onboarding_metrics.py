from __future__ import annotations

from mw.onboarding_metrics import format_markdown, summarize


def test_summarize_feedback_labels_and_close_time():
    issues = [
        {
            "title": "[feedback] lookup slow",
            "state": "CLOSED",
            "labels": [{"name": "feedback"}, {"name": "onboarding"}],
            "createdAt": "2026-11-23T10:00:00Z",
            "closedAt": "2026-11-23T14:00:00Z",
        },
        {
            "title": "[feedback] false positive",
            "state": "OPEN",
            "labels": [{"name": "feedback"}, {"name": "false-positive"}],
            "createdAt": "2026-11-23T12:00:00Z",
            "closedAt": None,
        },
        {"title": "unrelated", "state": "OPEN", "labels": [], "createdAt": None, "closedAt": None},
    ]
    result = summarize(issues)
    assert result["total"] == 2
    assert result["open"] == 1
    assert result["closed"] == 1
    assert result["labels"]["onboarding"] == 1
    assert result["median_time_to_close_hours"] == 4.0
    assert "Opt-in only" in format_markdown(result)
