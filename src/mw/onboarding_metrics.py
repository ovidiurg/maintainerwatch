from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from statistics import median
from typing import Any


def _labels(issue: dict[str, Any]) -> set[str]:
    return {
        str(item.get("name"))
        for item in (issue.get("labels") or [])
        if isinstance(item, dict) and item.get("name")
    }


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


STEP_LABELS = {
    "lookup": "package lookup",
    "ci": "ci workflow",
    "pr_comment": "pr comment",
    "repeat": "more than once",
}


def _steps(body: str) -> set[str]:
    completed = set()
    for line in body.splitlines():
        lowered = line.strip().lower()
        if not lowered.startswith("- [x]") and not lowered.startswith("- [X]"):
            continue
        for step, label in STEP_LABELS.items():
            if label in lowered:
                completed.add(step)
    return completed


def summarize(issues: list[dict[str, Any]]) -> dict[str, Any]:
    feedback = [
        issue for issue in issues
        if str(issue.get("title", "")).startswith("[feedback]") or "feedback" in _labels(issue)
    ]
    labels: Counter[str] = Counter()
    steps: Counter[str] = Counter()
    closed_hours: list[float] = []
    for issue in feedback:
        labels.update(_labels(issue))
        steps.update(_steps(str(issue.get("body") or "")))
        created = _parse(issue.get("createdAt"))
        closed = _parse(issue.get("closedAt"))
        if created and closed:
            closed_hours.append((closed - created).total_seconds() / 3600)
    open_count = sum(1 for issue in feedback if issue.get("state") == "OPEN")
    return {
        "total": len(feedback),
        "open": open_count,
        "closed": len(feedback) - open_count,
        "labels": dict(sorted(labels.items())),
        "self_reported_steps": dict(sorted(steps.items())),
        "median_time_to_close_hours": (
            round(median(closed_hours), 1) if closed_hours else None
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def format_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Onboarding feedback metrics",
        "",
        f"Total feedback issues: {summary['total']}",
        f"Open: {summary['open']}",
        f"Closed: {summary['closed']}",
        f"Median time to close: {summary['median_time_to_close_hours'] or 'n/a'} hours",
        "",
        "## Labels",
    ]
    if summary["labels"]:
        lines.extend(f"- {name}: {count}" for name, count in summary["labels"].items())
    else:
        lines.append("- none")
    lines.extend(["", "## Self-reported steps"])
    if summary.get("self_reported_steps"):
        lines.extend(
            f"- {name}: {count}"
            for name, count in summary["self_reported_steps"].items()
        )
    else:
        lines.append("- none")
    lines.extend([
        "",
        "Opt-in only: this measures public issue-form reports, not hidden site telemetry.",
    ])
    return "\n".join(lines) + "\n"
