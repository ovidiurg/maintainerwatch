from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from ..models import Maintainer, Package, Version
from .http import CachedClient

API = "https://crates.io/api/v1"
TOP = API + "/crates?per_page=100&page={page}&sort=downloads"

SEED_CRATES = [
    "serde", "serde_json", "tokio", "rand", "log", "regex", "clap", "anyhow",
    "thiserror", "reqwest", "hyper", "axum", "tracing", "futures", "bytes",
    "hashbrown", "indexmap", "itertools", "chrono", "uuid", "parking_lot",
    "rayon", "crossbeam", "num-traits", "memchr", "once_cell", "smallvec",
    "bitflags", "libc", "syn", "quote", "proc-macro2", "cc", "pkg-config",
    "openssl", "rustls", "ring", "base64", "hex", "sha2", "hmac", "aes",
    "zeroize", "subtle", "getrandom", "time", "url", "http", "mime",
    "percent-encoding", "idna", "toml", "bincode", "postcard", "prost",
    "tonic", "tower", "tower-http", "tracing-subscriber", "env_logger",
    "dotenv", "tempfile", "walkdir", "glob", "ignore", "notify", "async-trait",
    "pin-project", "futures-util", "tokio-util", "async-std", "smol", "mio",
    "slab", "socket2", "nix", "libloading", "bindgen", "which", "semver",
    "cargo_metadata", "rustc_version", "version_check", "autocfg",
]


def normalize_name(name: str) -> str:
    return name.strip().lower()


def fetch_top(client: CachedClient, top_n: int, seed_file: str | None = None) -> list[str]:
    if seed_file:
        names = [
            line.strip()
            for line in Path(seed_file).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
    else:
        names = []
        page = 1
        while len(names) < top_n and page <= 20:
            doc = client.get_json(TOP.format(page=page))
            crates = (doc or {}).get("crates") or []
            if not crates:
                break
            names.extend(c.get("name") for c in crates if c.get("name"))
            page += 1
        if not names:
            names = list(SEED_CRATES)
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out[:top_n]


def _latest_version(versions: list[dict]) -> dict | None:
    if not versions:
        return None
    return max(versions, key=lambda v: v.get("created_at") or "")


def fetch_package(client: CachedClient, name: str) -> tuple[Package, list[Version], list[Maintainer]] | None:
    doc = client.get_json(f"{API}/crates/{quote(name)}")
    if not doc or "crate" not in doc:
        return None
    crate = doc["crate"]
    raw_versions = doc.get("versions") or []
    latest = _latest_version(raw_versions)
    license = (latest or {}).get("license")

    versions = [
        Version(
            system="crates",
            name=name,
            version=v["num"],
            published_at=v.get("created_at"),
            has_sig=False,
            has_provenance=False,
            is_yanked=bool(v.get("yanked")),
        )
        for v in raw_versions
        if v.get("num")
    ]

    owners = client.get_json(f"{API}/crates/{quote(name)}/owners") or {}
    maintainers = []
    for user in owners.get("users") or []:
        ident = user.get("login") or user.get("name")
        if ident:
            maintainers.append(
                Maintainer(system="crates", name=name, identity=ident,
                           role=user.get("kind") or "owner", source="crates")
            )

    pkg = Package(
        system="crates",
        name=name,
        normalized=normalize_name(name),
        downloads_weekly=int(crate.get("recent_downloads") or crate.get("downloads") or 0),
        repo_url=crate.get("repository"),
        license=license,
        first_seen=crate.get("created_at"),
    )
    return pkg, versions, maintainers


def fetch_dependencies(client: CachedClient, name: str) -> list[str]:
    doc = client.get_json(f"{API}/crates/{quote(name)}")
    if not doc:
        return []
    latest = _latest_version(doc.get("versions") or [])
    if not latest:
        return []
    deps = client.get_json(
        f"{API}/crates/{quote(name)}/{quote(latest['num'])}/dependencies"
    )
    if not deps:
        return []
    return sorted(
        {
            d["crate_id"]
            for d in deps.get("dependencies", [])
            if d.get("crate_id") and d.get("kind") in ("normal", "build")
        }
    )
