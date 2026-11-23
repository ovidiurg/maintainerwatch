from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_feedback_issue_form_and_intake_workflow_are_wired():
    form = yaml.safe_load((ROOT / ".github/ISSUE_TEMPLATE/feedback.yml").read_text())
    assert "[feedback]" in form["title"]
    assert "feedback" in form["labels"]
    assert "needs-triage" in form["labels"]

    workflow = yaml.safe_load((ROOT / ".github/workflows/feedback-intake.yml").read_text())
    triggers = workflow.get("on", workflow.get(True))
    assert "issues" in triggers
    assert "opened" in triggers["issues"]["types"]
    assert workflow["permissions"]["issues"] == "write"
    assert (ROOT / "docs/feedback.md").exists()
