from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_package_lookup_assets_are_wired():
    html = (ROOT / "site/index.html").read_text(encoding="utf-8")
    script = (ROOT / "site/lookup.js").read_text(encoding="utf-8")
    pages = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")

    assert 'id="lookup"' in html
    assert 'id="lookup-form"' in html
    assert 'id="ci"' in html
    assert 'src="lookup.js"' in html
    assert 'ovidiurg/maintainerwatch@main' in html
    assert "maintainerwatch-index.json" in script
    assert "maintainerwatch-index.json" in pages
    start = (ROOT / "site/start.html").read_text(encoding="utf-8")
    assert "Your first 10 minutes" in start
    assert "index.html#lookup" in start
    assert "index.html#ci" in start
    assert (ROOT / "examples/github-action/.github/workflows/maintainerwatch.yml").exists()
    assert (ROOT / ".github/ISSUE_TEMPLATE/feedback.yml").exists()
