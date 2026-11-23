# MaintainerWatch GitHub Action template

Copy `.github/workflows/maintainerwatch.yml` into a repository, or use this
directory as the basis for a small template repository.

The workflow:

- runs only on `pull_request`;
- checks changed dependency manifests against the latest compact index;
- never downloads or executes package code;
- starts advisory with `fail-on: none`;
- posts one sticky PR comment and uploads SARIF.

## Before enabling blocking

Review the results in one or two real pull requests. Then set `fail-on: high`
and, if you want GitHub to block merges, require the `scan` check in branch
protection.

## Pin the action

For production, pin `ovidiurg/maintainerwatch@main` to a commit SHA or release
tag. Do not use `pull_request_target` for untrusted pull requests.

Full options and comment behaviour: `docs/pr-ci.md`.
