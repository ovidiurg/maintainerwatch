# PR/CI integration

`mw scan-diff` compares dependency manifests between two git revisions and
matches changed packages against a compact risk index. It does not execute
package code.

## Compact index

Build an index after `mw score-all`:

```bash
make ci-index
# or:
python scripts/build_ci_index.py --out dist/maintainerwatch-index.json
```

The index contains only `system`, `name`, `score`, `band`, `confidence`,
`coverage` and `risk_type`. It is versioned with `model_version`; publish the
JSON and its `.sha256` as an immutable release asset.

The index is built from the local database, so it is not generated in a
GitHub-hosted CI job without the database. Generate/publish it from the trusted
maintainer environment:

```bash
make ci-index
DRY_RUN=1 make ci-publish-index   # inspect the planned release
make ci-publish-index
```

`ci-publish-index` creates a versioned `ci-index-YYYYMMDD` release, uploads a
versioned JSON + checksum and the fixed `maintainerwatch-index.json` latest
asset. It requires authenticated `gh` and a public repository for external
consumers.

## How it works in a real PR

1. The repository owner adds one workflow once (see the action example below).
2. A contributor opens or updates a PR that changes a dependency manifest.
3. GitHub starts the workflow on `pull_request`.
4. The action downloads the compact index and runs `mw scan-diff` against the
   PR base.
5. Only added or version-changed packages are looked up; package code is never
   downloaded or executed.
6. Results are written to SARIF and the check summary.
7. If `comment: true`, one sticky PR comment is created or updated.

The action does nothing to the PR when no manifest changed or when no changed
package reaches the configured threshold.

### Comment lifecycle

With the default `comment: false`, no PR comments are created. SARIF and the
check summary remain the primary output.

With `comment: true`:

- one marker comment is used:
  `<!-- maintainerwatch:pr-summary -->`;
- further pushes update that comment instead of creating another one;
- only medium/high findings are included;
- deleting the comment manually is safe; a later run creates a fresh one;
- a run with no relevant findings does not add a new comment.

Example:

```text
### MaintainerWatch

1 risky changed package(s):

- **high** npm/test-pkg version 1.0.1: Maintainer takeover
  (score 80.0, band high, confidence high)
```

Do not use `pull_request_target` for untrusted pull requests. On forked PRs the
default token is read-only; skip the comment step or use a trusted follow-up
workflow rather than exposing secrets.

## Local use

```bash
mw scan-diff \
  --base origin/main \
  --head HEAD \
  --index dist/maintainerwatch-index.json \
  --format sarif \
  --out maintainerwatch.sarif \
  --fail-on none
```

Default policy is advisory: `--fail-on none`. Use `medium` or `high` only after
local validation.

## GitHub Action

The composite action installs the action checkout by default (the package is
not yet published on PyPI), downloads the index, verifies its optional SHA-256,
runs `mw scan-diff`, uploads SARIF and can optionally maintain **one** sticky PR
comment. `package-spec` can override the install source with a published wheel
or public Git URL.

```yaml
- uses: ovidiurg/maintainerwatch@main
  with:
    index-url: https://github.com/ovidiurg/maintainerwatch/releases/latest/download/maintainerwatch-index.json
    index-sha256: ${{ vars.MAINTAINERWATCH_INDEX_SHA256 }}
    base-ref: origin/${{ github.base_ref }}
    fail-on: none
    comment: false
    upload-sarif: true
```

`index-path` is available for private/offline tests and takes precedence over
`index-url`. `upload-sarif: false` is useful on environments without code
scanning.

Required permissions:

```yaml
permissions:
  contents: read
  security-events: write
  pull-requests: write  # only when comment: true
```

`comment` is **false by default**. When enabled, the action updates one marker
comment (`<!-- maintainerwatch:pr-summary -->`) instead of creating a comment
per package or per push. Do not use `pull_request_target` for untrusted PRs.

## Limitations

- The action currently supports npm and PyPI manifests.
- Lockfile parsing is metadata-only; no package code is downloaded or executed.
- Index freshness is tied to the published artifact and `model_version`.
- The repository must be public for a public Release asset and external action
  use; until then use a local index path or authenticated artifact.
