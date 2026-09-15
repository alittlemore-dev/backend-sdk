# Backend SDK

## Scope

- This repository owns the publishable `alittlemore-backend-sdk` distribution and
  the `backend_sdk` Python import package.
- Shared integrations, domain building blocks, middleware, helpers, utilities, and
  factories belong here when they have a concrete reusable purpose. Product-specific
  workflows, application entrypoints, deployment, and secrets belong to consuming services.
- The initial scaffold contains no runtime functionality. Add modules only for requested
  behavior; do not pre-create empty architectural layers or placeholder integrations.

## Package boundaries

- Support at most two Python minor versions: the latest stable release and its immediate
  predecessor, including all patch releases in both lines (currently 3.14.x and 3.13.x).
  Prereleases do not advance this support window. When a new stable minor is released,
  move the window forward and update package metadata, CI, tooling, and documentation together.
- Bound `requires-python` to this window. Run CI on both minor versions without patch pins;
  target the oldest supported version in Ruff and mypy. Use the latest supported minor
  for `.python-version` and release artifacts.
- Use a `src/backend_sdk/` layout, uv, and `pyproject.toml` configuration.
- Keep the base installation minimal. Introduce integration dependencies through named
  extras when the corresponding integration exists. Importing the base package must not
  require optional integrations or perform configuration, I/O, or service startup.
- Keep reusable domain objects independent of web frameworks, persistence, and application
  configuration. Accept configuration explicitly from consumers.
- Preserve `py.typed` and annotate public APIs. Treat public imports and dependency changes
  as compatibility decisions; record user-visible changes in `CHANGELOG.md`.
- Keep the version in `pyproject.toml`; release tags must match `v<version>` exactly.

## Development and verification

- Use `make help` for supported commands. Keep Make targets thin and command orchestration
  in `scripts/`; CI must call the same commands used locally.
- Commit `uv.lock` when dependencies change intentionally. Normal installation and checks
  use locked dependencies; do not silently regenerate the lock during verification.
- Run `make quality` before reporting completion. Report failed or unavailable checks.
- Test actual behavior and installed distributions. Keep test-only helpers under `tests/`.
- The empty scaffold has no meaningful runtime coverage. Once executable library code is
  introduced, include `make coverage` in `quality`; preserve the configured 95% branch
  coverage threshold and add behavior tests in that same change.
- Update both `.github/README.md` and `.github/README_RU.md` for changes to public setup or
  developer commands. Keep agent guidance in English.
- Do not publish, push, tag, or modify repository settings without task authorization.
  Release setup instructions do not authorize an actual release.
