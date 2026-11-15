from __future__ import annotations

import tomllib
from pathlib import Path

from mw import MODEL_VERSION, __version__
from mw.config import load_config

ROOT = Path(__file__).resolve().parents[1]


def test_versions_are_consistent_across_package_and_configs():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == __version__

    default = load_config(ROOT / "config/default.yaml")
    assert default.model_version == MODEL_VERSION
    for path in sorted((ROOT / "config").glob("validation*.yaml")):
        assert load_config(path).model_version == MODEL_VERSION, path.name
