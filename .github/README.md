# Backend SDK

[Русский](https://github.com/alittlemore-dev/backend-sdk/blob/main/.github/README_RU.md)

Shared backend library for **alittlemore.dev**: integrations, domain objects,
middleware, helpers, utilities, and factories. Currently infrastructure only.

**Package:** `alittlemore-backend-sdk` · **Import:** `backend_sdk` · **License:** MIT

**Python:** latest stable minor + its predecessor, all patch releases; currently 3.14.x and 3.13.x.

**Tooling:** uv, Hatchling, Ruff, mypy, pytest, Bandit, pip-audit, Twine.

## Development

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and GNU Make.

```sh
make install   # Install dependencies
make quality   # Run all checks
make build     # Build wheel and sdist
make help      # List commands
```

[Releases](https://github.com/alittlemore-dev/backend-sdk/blob/main/.github/RELEASING.md)
· [Changelog](https://github.com/alittlemore-dev/backend-sdk/blob/main/CHANGELOG.md)
