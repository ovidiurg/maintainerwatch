from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from ..models import Maintainer, Package, Version
from .http import CachedClient

REGISTRY = "https://registry.npmjs.org"
DOWNLOADS = "https://api.npmjs.org/downloads/point/last-week"
NPMS_SEARCH = "https://api.npms.io/v2/search"

# Curated seed for offline/smoke runs. For large runs, pass --seed-file with a
# newline-separated list (e.g. an npm high-impact ranking).
SEED_NPM = [
    "lodash", "react", "react-dom", "axios", "express", "chalk", "commander",
    "debug", "tslib", "uuid", "moment", "dayjs", "rxjs", "zod", "yargs",
    "glob", "minimist", "semver", "mkdirp", "rimraf", "fs-extra", "dotenv",
    "body-parser", "cors", "helmet", "morgan", "cookie-parser", "jsonwebtoken",
    "bcrypt", "passport", "mongoose", "sequelize", "pg", "mysql2", "redis",
    "ioredis", "knex", "prisma", "typeorm", "graphql", "apollo-server",
    "socket.io", "ws", "undici", "node-fetch", "cross-fetch", "form-data",
    "multer", "sharp", "jimp", "canvas", "pdfkit", "xlsx", "csv-parse",
    "papaparse", "cheerio", "jsdom", "puppeteer", "playwright", "esbuild",
    "webpack", "rollup", "vite", "parcel", "babel-core", "@babel/core",
    "typescript", "ts-node", "eslint", "prettier", "jest", "mocha", "chai",
    "vitest", "tap", "ava", "nodemon", "pm2", "concurrently", "npm-run-all",
    "cross-env", "rimraf", "del", "globby", "fast-glob", "chokidar", "ws",
    "event-stream", "ua-parser-js", "colors", "node-ipc",
]


def normalize_name(name: str) -> str:
    return name.strip().lower()


def parse_repo_url(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("git+"):
        value = value[4:]
    if value.startswith("git://"):
        value = "https://" + value[6:]
    if value.endswith(".git"):
        value = value[:-4]
    return value


def _repo_url(doc: dict) -> str | None:
    repo = doc.get("repository")
    if isinstance(repo, dict):
        return parse_repo_url(repo.get("url"))
    if isinstance(repo, str):
        return parse_repo_url(repo)
    return None


def _license(doc: dict) -> str | None:
    lic = doc.get("license")
    if isinstance(lic, dict):
        return lic.get("type")
    if isinstance(lic, str):
        return lic
    return None


def _npms_names(client: CachedClient, top_n: int) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    offset = 0
    while len(names) < top_n and offset < 10_000:
        doc = client.get_json(
            f"{NPMS_SEARCH}?q=not:unstable&size=250&from={offset}"
        )
        results = (doc or {}).get("results") or []
        if not results:
            break
        for r in results:
            name = (r.get("package") or {}).get("name")
            if name and name not in seen:
                seen.add(name)
                names.append(name)
                if len(names) >= top_n:
                    break
        offset += 250
    return names


def fetch_top(client: CachedClient, top_n: int, seed_file: str | None = None) -> list[str]:
    if seed_file:
        names = [
            line.strip()
            for line in Path(seed_file).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
    else:
        names = _npms_names(client, top_n)
        if not names:
            names = list(SEED_NPM)
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out[:top_n]


def fetch_package(client: CachedClient, name: str) -> tuple[Package, list[Version], list[Maintainer]] | None:
    url = f"{REGISTRY}/{quote(name, safe='')}"
    doc = client.get_json(url)
    if not doc or "versions" not in doc:
        return None

    times = doc.get("time", {}) or {}
    versions: list[Version] = []
    for ver, meta in (doc.get("versions") or {}).items():
        dist = meta.get("dist") or {}
        user = meta.get("_npmUser") or {}
        versions.append(
            Version(
                system="npm",
                name=name,
                version=ver,
                published_at=times.get(ver),
                publisher_name=user.get("name"),
                publisher_email=user.get("email"),
                has_sig=bool(dist.get("signatures")),
                has_provenance=bool(dist.get("attestations")),
                is_yanked=bool(meta.get("deprecated")),
            )
        )

    maintainers: list[Maintainer] = []
    for m in doc.get("maintainers") or []:
        ident = (m.get("name") or m.get("email") or "").strip()
        if not ident:
            continue
        maintainers.append(
            Maintainer(system="npm", name=name, identity=ident,
                       role="maintainer", source="npm")
        )

    pkg = Package(
        system="npm",
        name=name,
        normalized=normalize_name(name),
        repo_url=_repo_url(doc),
        license=_license(doc),
        first_seen=times.get("created"),
    )
    return pkg, versions, maintainers


def fetch_downloads(client: CachedClient, name: str) -> int:
    doc = client.get_json(f"{DOWNLOADS}/{quote(name, safe='')}")
    if not doc:
        return 0
    try:
        return int(doc.get("downloads") or 0)
    except (TypeError, ValueError):
        return 0


def fetch_dependencies(client: CachedClient, name: str) -> list[str]:
    doc = client.get_json(f"{REGISTRY}/{quote(name, safe='')}")
    if not doc:
        return []
    latest = (doc.get("dist-tags") or {}).get("latest")
    meta = (doc.get("versions") or {}).get(latest) or {}
    return sorted((meta.get("dependencies") or {}).keys())