from __future__ import annotations

import hashlib
import io
import json
import re
import tarfile
import zipfile
from urllib.parse import quote

from .http import CachedClient

NPM_REGISTRY = "https://registry.npmjs.org"
PYPI_JSON = "https://pypi.org/pypi"
CRATES_DOWNLOAD = "https://crates.io/api/v1/crates/{name}/{version}/download"

TEXT_EXTENSIONS = {
    ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".py", ".rb", ".php",
    ".sh", ".bash", ".json", ".toml", ".yml", ".yaml", ".go", ".rs",
}
BINARY_EXTENSIONS = {".exe", ".dll", ".so", ".dylib", ".node", ".wasm", ".bin"}

PATTERNS = {
    "network_exec": re.compile(r"\b(curl|wget)\b[^\n]{0,160}\|\s*(sh|bash)\b", re.I),
    "base64": re.compile(r"\b(base64|atob)\b|Buffer\.from\([^,]+,\s*['\"]base64", re.I),
    "wallet": re.compile(r"\b(wallet|metamask|mnemonic|private[_ -]?key|solana|ethereum)\b", re.I),
    "env_access": re.compile(r"process\.env|os\.environ|AWS_[A-Z_]*(KEY|SECRET)|GITHUB_TOKEN", re.I),
    "child_process": re.compile(r"child_process|subprocess|os\.system|execSync|spawnSync", re.I),
    "eval": re.compile(r"\beval\s*\(|\bFunction\s*\(", re.I),
    "network": re.compile(r"https?://|requests\.post|fetch\s*\(|axios\.", re.I),
    "long_base64": re.compile(r"[A-Za-z0-9+/]{300,}={0,2}"),
}

WEIGHTS = {
    "network_exec": 40,
    "wallet": 25,
    "env_access": 15,
    "base64": 15,
    "child_process": 8,
    "eval": 8,
    "long_base64": 15,
    "binary": 8,
    "install_hook": 12,
    "network": 3,
}


def _archive_url(client: CachedClient, system: str, name: str, version: str) -> str | None:
    if system == "npm":
        doc = client.get_json(f"{NPM_REGISTRY}/{quote(name, safe='')}")
        if not isinstance(doc, dict):
            return None
        meta = (doc.get("versions") or {}).get(version) or {}
        return ((meta.get("dist") or {}).get("tarball")) or None
    if system == "pypi":
        doc = client.get_json(f"{PYPI_JSON}/{quote(name, safe='')}/{quote(version, safe='')}/json")
        if not isinstance(doc, dict):
            return None
        files = doc.get("urls") or []
        candidates = [
            item for item in files
            if (item.get("filename") or "").endswith((".tar.gz", ".zip", ".whl"))
        ]
        candidates.sort(key=lambda item: 0 if item.get("filename", "").endswith((".tar.gz", ".zip")) else 1)
        return candidates[0].get("url") if candidates else None
    if system == "crates":
        return CRATES_DOWNLOAD.format(name=quote(name, safe=""), version=quote(version, safe=""))
    return None


def fetch_archive(
    client: CachedClient,
    system: str,
    name: str,
    version: str,
    max_bytes: int = 20_000_000,
) -> tuple[bytes, str] | None:
    url = _archive_url(client, system, name, version)
    if not url:
        return None
    data = client.get_bytes(url, max_bytes=max_bytes)
    if not data:
        return None
    return data, url.rsplit("/", 1)[-1]


def scan_archive(data: bytes, filename: str) -> dict:
    files: list[str] = []
    total_bytes = 0
    text_bytes = 0
    flags: set[str] = set()
    binary = 0
    install_hook = False

    def inspect(name: str, payload: bytes) -> None:
        nonlocal total_bytes, text_bytes, binary, install_hook
        total_bytes += len(payload)
        files.append(name[:300])
        lower = name.lower()
        extension = "." + lower.rsplit(".", 1)[-1] if "." in lower else ""
        if extension in BINARY_EXTENSIONS:
            binary += 1
            flags.add("binary")
            return
        if extension not in TEXT_EXTENSIONS or len(payload) > 1_000_000:
            return
        text = payload.decode("utf-8", errors="ignore")
        text_bytes += len(payload)
        if lower.endswith("package.json"):
            try:
                scripts = (json.loads(text).get("scripts") or {})
                if any(key in scripts for key in ("preinstall", "install", "postinstall")):
                    install_hook = True
            except (ValueError, AttributeError):
                pass
        if lower.endswith(("setup.py", "pyproject.toml")) and "install" in text:
            install_hook = True
        for flag, pattern in PATTERNS.items():
            if pattern.search(text):
                flags.add(flag)

    try:
        if tarfile.is_tarfile(io.BytesIO(data)):
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
                for member in archive.getmembers()[:5000]:
                    if not member.isfile() or member.size > 5_000_000:
                        continue
                    handle = archive.extractfile(member)
                    if handle is None:
                        continue
                    payload = handle.read(1_000_000)
                    inspect(member.name, payload)
                    if total_bytes > 50_000_000 or text_bytes > 8_000_000:
                        break
        elif zipfile.is_zipfile(io.BytesIO(data)):
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                for info in archive.infolist()[:5000]:
                    if info.is_dir() or info.file_size > 5_000_000:
                        continue
                    payload = archive.read(info)[:1_000_000]
                    inspect(info.filename, payload)
                    if total_bytes > 50_000_000 or text_bytes > 8_000_000:
                        break
        else:
            flags.add("unrecognised_archive")
    except (tarfile.TarError, zipfile.BadZipFile, OSError):
        flags.add("archive_error")

    if install_hook:
        flags.add("install_hook")
    score = min(100, sum(WEIGHTS.get(flag, 0) for flag in flags))
    return {
        "risk_score": score,
        "flags": sorted(flags),
        "files": len(files),
        "bytes": total_bytes,
        "sha256": hashlib.sha256(data).hexdigest(),
        "sample_files": files[:50],
    }
