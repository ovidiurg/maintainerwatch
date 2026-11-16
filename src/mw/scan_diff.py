from __future__ import annotations

import json
import re
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

MANIFEST_NAMES = {
    "package.json": "npm",
    "package-lock.json": "npm",
    "requirements.txt": "pypi",
    "requirements-dev.txt": "pypi",
    "pyproject.toml": "pypi",
    "poetry.lock": "pypi",
    "Pipfile.lock": "pypi",
}
REQUIREMENTS_RE = re.compile(r"^\s*([A-Za-z0-9@][A-Za-z0-9._@/-]*)\s*(?:\[[^\]]*\])?\s*(==|>=|<=|~=|>|<)?\s*([^\s;#]+)?")


@dataclass(frozen=True)
class PackageChange:
    system: str
    name: str
    version: str | None
    old_version: str | None
    path: str


def manifest_system(path: str) -> str | None:
    name = Path(path).name
    if name in MANIFEST_NAMES:
        return MANIFEST_NAMES[name]
    if name.startswith("requirements") and name.endswith(".txt"):
        return "pypi"
    return None


def _norm_pypi(name: str) -> str:
    return canonicalize_name(name)


def _req_name_version(line: str) -> tuple[str, str | None] | None:
    line = line.strip()
    if not line or line.startswith(("#", "-", "git+", "http:", "https:")):
        return None
    try:
        req = Requirement(line)
    except InvalidRequirement:
        match = REQUIREMENTS_RE.match(line)
        if not match:
            return None
        return _norm_pypi(match.group(1)), match.group(3)
    version = None
    for spec in req.specifier:
        if spec.operator == "==":
            version = spec.version
            break
    return _norm_pypi(req.name), version


def parse_manifest(path: str, text: str) -> dict[str, str | None]:
    system = manifest_system(path)
    if not system:
        return {}
    name = Path(path).name
    out: dict[str, str | None] = {}
    if system == "npm":
        if name == "package-lock.json":
            doc = json.loads(text)
            for key, meta in (doc.get("packages") or {}).items():
                if not key or not isinstance(meta, dict) or not meta.get("version"):
                    continue
                package = key.rsplit("node_modules/", 1)[-1]
                if package:
                    out[package] = str(meta["version"])
        else:
            doc = json.loads(text)
            for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
                for package, version in (doc.get(section) or {}).items():
                    out[package] = str(version)
        return out
    if name == "requirements.txt" or name.startswith("requirements"):
        for line in text.splitlines():
            item = _req_name_version(line)
            if item:
                out[item[0]] = item[1]
        return out
    if name == "pyproject.toml":
        doc = tomllib.loads(text)
        project = doc.get("project") or {}
        deps: list[str] = list(project.get("dependencies") or [])
        for values in (project.get("optional-dependencies") or {}).values():
            deps.extend(values or [])
        poetry = ((doc.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
        for package, spec in poetry.items():
            if package.lower() == "python":
                continue
            if isinstance(spec, str):
                deps.append(f"{package}{spec}" if spec.startswith(("=", ">", "<", "~", "^")) else f"{package}=={spec}")
            elif isinstance(spec, dict) and spec.get("version"):
                deps.append(f"{package}{spec['version']}")
        for dep in deps:
            item = _req_name_version(dep)
            if item:
                out[item[0]] = item[1]
        return out
    if name == "poetry.lock":
        doc = tomllib.loads(text)
        for package in doc.get("package") or []:
            if package.get("name"):
                out[_norm_pypi(package["name"])] = str(package.get("version")) if package.get("version") else None
        return out
    if name == "Pipfile.lock":
        doc = json.loads(text)
        for section in ("default", "develop"):
            for package, meta in (doc.get(section) or {}).items():
                version = (meta or {}).get("version") if isinstance(meta, dict) else None
                out[_norm_pypi(package)] = str(version).lstrip("=") if version else None
        return out
    return out


def diff_maps(base: dict[str, str | None], head: dict[str, str | None]) -> list[tuple[str, str | None, str | None]]:
    out = []
    for name, version in head.items():
        if name not in base or base[name] != version:
            out.append((name, version, base.get(name)))
    return sorted(out)


def _git_show(root: Path, ref: str, path: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"{ref}:{path}"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def diff_manifests(base: str, head: str, root: str | Path = ".") -> list[PackageChange]:
    root = Path(root)
    changed = subprocess.run(
        ["git", "-C", str(root), "diff", "--name-only", "--diff-filter=ACMR", f"{base}...{head}"],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    changes: list[PackageChange] = []
    for path in changed:
        system = manifest_system(path)
        if not system:
            continue
        head_text = (root / path).read_text(encoding="utf-8", errors="replace")
        base_text = _git_show(root, base, path) or "{}"
        before = parse_manifest(path, base_text)
        after = parse_manifest(path, head_text)
        for name, version, old_version in diff_maps(before, after):
            changes.append(PackageChange(system, name, version, old_version, path))
    return changes


def load_index(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def lookup(index: dict, system: str, name: str) -> dict | None:
    package_map = index.get("packages") or {}
    keys = [f"{system}:{name}"]
    if system == "pypi":
        keys.append(f"pypi:{canonicalize_name(name)}")
    for key in keys:
        if key in package_map:
            return package_map[key]
    return None


def findings_for(changes: Iterable[PackageChange], index: dict) -> list[dict]:
    out = []
    for change in changes:
        match = lookup(index, change.system, change.name)
        if not match:
            continue
        item = dict(match)
        item.update({
            "path": change.path,
            "old_version": change.old_version,
            "version": change.version,
        })
        out.append(item)
    rank = {"high": 3, "medium": 2, "low": 1}
    return sorted(out, key=lambda item: (-rank.get(item.get("band"), 0), -float(item.get("score") or 0), item["name"]))


def summary(findings: list[dict], changes: int) -> dict:
    bands: dict[str, int] = {}
    for item in findings:
        bands[item.get("band", "unknown")] = bands.get(item.get("band", "unknown"), 0) + 1
    return {
        "changed_packages": changes,
        "matched_packages": len(findings),
        "bands": bands,
        "findings": findings,
    }


def sarif(findings: list[dict], model_version: str | None = None) -> dict:
    level = {"high": "error", "medium": "warning", "low": "note"}
    rules = [
        {"id": "maintainerwatch-high", "name": "High maintainer risk", "shortDescription": {"text": "High MaintainerWatch risk"}},
        {"id": "maintainerwatch-medium", "name": "Medium maintainer risk", "shortDescription": {"text": "Medium MaintainerWatch risk"}},
        {"id": "maintainerwatch-low", "name": "Low maintainer risk", "shortDescription": {"text": "Low MaintainerWatch risk"}},
    ]
    results = []
    for item in findings:
        band = item.get("band", "low")
        message = (
            f"{item.get('system')}/{item.get('name')} version {item.get('version') or '?'}: "
            f"{item.get('risk_type') or 'risk indicator'} (score {item.get('score')}, "
            f"band {band}, confidence {item.get('confidence') or 'unknown'})"
        )
        results.append({
            "ruleId": f"maintainerwatch-{band}",
            "level": level.get(band, "note"),
            "message": {"text": message},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": item.get("path") or "manifest"},
                    "region": {"startLine": 1},
                }
            }],
            "properties": {
                "system": item.get("system"),
                "name": item.get("name"),
                "version": item.get("version"),
                "score": item.get("score"),
                "band": band,
                "confidence": item.get("confidence"),
            },
        })
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "MaintainerWatch",
                    "informationUri": "https://github.com/ovidiurg/maintainerwatch",
                    "version": model_version or "unknown",
                    "rules": rules,
                }
            },
            "results": results,
        }],
    }
