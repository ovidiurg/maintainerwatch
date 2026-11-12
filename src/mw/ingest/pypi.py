from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from ..models import Maintainer, Package, Version
from .http import CachedClient

PYPI = "https://pypi.org/pypi"
PYPISTATS = "https://pypistats.org/api/packages"
TOP_PYPI = (
    "https://raw.githubusercontent.com/hugovk/top-pypi-packages/main/"
    "top-pypi-packages-30-days.min.json"
)

SEED_PYPI = [
    "requests", "urllib3", "certifi", "charset-normalizer", "idna", "numpy",
    "pandas", "python-dateutil", "pytz", "six", "setuptools", "pip", "wheel",
    "packaging", "pyyaml", "click", "jinja2", "markupsafe", "flask", "django",
    "fastapi", "starlette", "pydantic", "sqlalchemy", "alembic", "psycopg2-binary",
    "redis", "celery", "kombu", "boto3", "botocore", "s3transfer", "jmespath",
    "google-auth", "protobuf", "grpcio", "httpx", "aiohttp", "websockets",
    "cryptography", "pyopenssl", "paramiko", "bcrypt", "pyjwt", "passlib",
    "pytest", "coverage", "black", "ruff", "mypy", "isort", "flake8", "pylint",
    "tox", "nox", "virtualenv", "pipenv", "poetry", "hatchling", "twine",
    "build", "rich", "tqdm", "colorama", "tabulate", "matplotlib", "seaborn",
    "scipy", "scikit-learn", "torch", "tensorflow", "transformers", "pillow",
    "opencv-python", "lxml", "beautifulsoup4", "scrapy", "selenium", "playwright",
    "openpyxl", "xlrd", "docutils", "sphinx", "mkdocs", "jupyter", "notebook",
    "ipython", "ctx", "requests-toolbelt",
]


def normalize_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def fetch_top(client: CachedClient, top_n: int, seed_file: str | None = None) -> list[str]:
    if seed_file:
        names = [
            line.strip()
            for line in Path(seed_file).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        return names[:top_n]
    doc = client.get_json(TOP_PYPI)
    names: list[str] = []
    if isinstance(doc, dict) and isinstance(doc.get("rows"), list):
        names = [row.get("project") for row in doc["rows"] if row.get("project")]
    if not names:
        names = list(SEED_PYPI)
    return names[:top_n]


def _looks_like_repo(url: str | None) -> bool:
    if not url:
        return False
    lowered = url.lower()
    if any(
        bad in lowered
        for bad in ("/blob/", "/tree/", "/issues", "/discussions", "/wiki", "/.github/")
    ):
        return False
    return (
        any(
            host in lowered
            for host in ("github.com", "gitlab.com", "bitbucket.org", "codeberg.org")
        )
        or lowered.endswith(".git")
    )


def _repo_url(info: dict) -> str | None:
    urls = info.get("project_urls") or {}
    candidates: list[tuple[str, str]] = []
    if isinstance(urls, dict):
        for key, value in urls.items():
            if not key or not value:
                continue
            lowered = key.lower()
            if any(
                bad in lowered
                for bad in (
                    "conduct", "issue", "changelog", "documentation", "docs",
                    "wiki", "funding", "sponsor", "chat", "discord", "slack",
                    "twitter", "mastodon", "blog",
                )
            ):
                continue
            candidates.append((lowered, value))

    def score(item: tuple[str, str]) -> int:
        key, value = item
        points = 0
        if "repo" in key or "source" in key:
            points += 3
        if any(host in key for host in ("github", "gitlab", "codeberg")):
            points += 3
        if "code" in key:
            points += 1
        if any(
            host in value.lower()
            for host in ("github.com", "gitlab.com", "bitbucket.org", "codeberg.org")
        ):
            points += 2
        if not _looks_like_repo(value):
            points -= 5
        return points

    candidates.sort(key=score, reverse=True)
    for candidate in candidates:
        if score(candidate) > 0 and _looks_like_repo(candidate[1]):
            return candidate[1]

    home = info.get("home_page")
    return home if _looks_like_repo(home) else None


def _license(info: dict) -> str | None:
    expression = (info.get("license_expression") or "").strip()
    if expression:
        return expression
    lic = (info.get("license") or "").strip()
    if lic and len(lic) < 200 and lic.upper() not in {"UNKNOWN", "NOASSERTION"}:
        return lic
    return _classifier(info)


def _classifier(info: dict) -> str | None:
    for classifier in info.get("classifiers") or []:
        if classifier.startswith("License ::"):
            return classifier.split("::")[-1].strip()
    return None


def fetch_package(client: CachedClient, name: str) -> tuple[Package, list[Version], list[Maintainer]] | None:
    doc = client.get_json(f"{PYPI}/{quote(name, safe='')}/json")
    if not doc or "info" not in doc:
        return None
    info = doc["info"]
    releases = doc.get("releases") or {}

    author = (info.get("author") or "").strip()
    maintainer = (info.get("maintainer") or "").strip()
    author_email = (info.get("author_email") or "").strip()
    maintainer_email = (info.get("maintainer_email") or "").strip()
    publisher_name = maintainer or author or None
    publisher_email = maintainer_email or author_email or None

    versions: list[Version] = []
    for ver, files in releases.items():
        files = files or []
        times = [f.get("upload_time_iso_8601") or f.get("upload_time") for f in files]
        times = [t for t in times if t]
        published_at = min(times) if times else None
        has_sig = any(bool(f.get("has_sig")) for f in files)
        has_provenance = any(bool(f.get("provenance") or f.get("has_provenance")) for f in files)
        is_yanked = any(bool(f.get("yanked")) for f in files) if files else False
        if not files:
            continue
        versions.append(
            Version(
                system="pypi", name=name, version=ver,
                published_at=published_at,
                publisher_name=publisher_name,
                publisher_email=publisher_email,
                has_sig=has_sig, has_provenance=has_provenance,
                is_yanked=is_yanked,
            )
        )

    maintainers: list[Maintainer] = []
    for ident, source in ((author, "author"), (maintainer, "maintainer")):
        if ident:
            maintainers.append(
                Maintainer(system="pypi", name=name, identity=ident,
                           role=source, source="pypi")
            )

    pkg = Package(
        system="pypi",
        name=name,
        normalized=normalize_name(name),
        repo_url=_repo_url(info),
        license=_license(info),
        license_classifier=_classifier(info),
        first_seen=min((v.published_at for v in versions if v.published_at), default=None),
    )
    return pkg, versions, maintainers


def fetch_downloads(client: CachedClient, name: str) -> int:
    doc = client.get_json(f"{PYPISTATS}/{quote(name, safe='')}/recent")
    if not doc:
        return 0
    try:
        return int((doc.get("data") or {}).get("last_week") or 0)
    except (TypeError, ValueError):
        return 0


def _requirement_name(requirement: str) -> str | None:
    text = requirement.split(";", 1)[0].strip()
    for separator in ("[", " ", "(", "<", ">", "=", "!", "~"):
        text = text.split(separator, 1)[0]
    text = text.strip().lower().replace("_", "-").replace(".", "-")
    return text or None


def fetch_dependencies(client: CachedClient, name: str) -> list[str]:
    doc = client.get_json(f"{PYPI}/{quote(name, safe='')}/json")
    if not doc:
        return []
    requirements = (doc.get("info") or {}).get("requires_dist") or []
    return sorted(
        {parsed for r in requirements if r for parsed in [_requirement_name(r)] if parsed}
    )
