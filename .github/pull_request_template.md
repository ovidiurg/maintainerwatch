## Summary

<!-- What changed and why? -->

## Testing

- [ ] Added/updated tests for the behavior change
- [ ] `pytest` passes
- [ ] Coverage is at least 75%
- [ ] `python -m compileall -q src scripts tests` passes
- [ ] `mw --help` and the affected command help were checked
- [ ] `mw calibrate` was run if model weights or scoring changed
- [ ] Docker smoke was run if code, Dockerfile, `pyproject.toml`, `docker-compose.yml` or `config/` changed (`make docker-smoke`)

## Documentation

- [ ] README/docs/AGENTS and generated numbers are updated
- [ ] No local `data/`, caches, reports, tokens or credentials are included
