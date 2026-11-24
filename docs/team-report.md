# Static team report

Generate an HTML or JSON report for dependency manifests in a repository:

```bash
mw team-report \
  --root . \
  --index dist/maintainerwatch-index.json \
  --waivers .maintainerwatch/waivers.yml \
  --out data/team-report.html
```

The report:

- scans `package.json`, `package-lock.json`, `requirements*.txt`,
  `pyproject.toml`, `poetry.lock` and `Pipfile.lock`;
- looks up packages in the compact public index;
- shows band, score, confidence, risk type and top signals;
- applies expiring waivers when supplied;
- writes a static HTML file or `--format json`.

No package code is executed and no database is required. Use it for a weekly
repository review or a static report artifact in CI.
