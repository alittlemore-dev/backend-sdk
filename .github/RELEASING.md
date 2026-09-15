# Releasing

## One-time setup

- Register `alittlemore-backend-sdk` as a pending [PyPI Trusted Publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/), subject to name availability:
  owner `alittlemore-dev`, repository `backend-sdk`, workflow `release.yaml`, environment `pypi`.
- Create the GitHub `pypi` environment with release-tag restrictions and required reviewers
  where available. Require the CI quality check for changes to `main`.

## Publish

1. Set the version in `pyproject.toml`, run `make lock`, and update `CHANGELOG.md`.
2. Run `make quality` and merge the reviewed changes.
3. Publish a GitHub Release from that commit with the exact tag `v<version>`.

The workflow verifies the version, reruns CI, and uploads the checked artifacts to PyPI
via OIDC. Publishing a GitHub Release triggers an actual upload, including prereleases.
