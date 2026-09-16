# Backend SDK

[Русский](https://github.com/alittlemore-dev/backend-sdk/blob/main/.github/README_RU.md)

Shared backend library for **alittlemore.dev**: integrations, domain objects,
middleware, helpers, utilities, and factories.

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

## Auth API integration

Install the Litestar integration:

```sh
uv add 'alittlemore-backend-sdk[litestar]'
```

```python
from backend_sdk.auth import RoleEnum
from backend_sdk.auth.http import AuthApiClientConfig
from backend_sdk.integrations.litestar import AuthPlugin, RequireRole
from litestar import Litestar, get


@get("/health", opt={"auth_public": True})
async def health() -> dict[str, str]:
    return {"status": "ok"}


app = Litestar(
    route_handlers=[health],
    plugins=[
        AuthPlugin(
            config=AuthApiClientConfig(
                verify_url="https://auth.example.com/api/auth/verify",
                timeout_seconds=2,
                cache_ttl_seconds=15,
                max_cache_entries=10_000,
            ),
        ),
    ],
)
```

Routes require a bearer token by default. Mark anonymous routes with
`opt={"auth_public": True}` and protect privileged routes with
`RequireRole(RoleEnum.ADMIN)`. Successful checks are cached in each process for
at most 15 seconds; set `cache_ttl_seconds=0` to disable this. Services must
still enforce resource ownership in their own domain logic.

The cache is intentionally process-local: it is a short availability and latency
optimization, adds no infrastructure dependency, and never becomes an authorization
source of truth. Each process can perform one auth-api request per token and TTL.

See [`examples/litestar_auth.py`](../examples/litestar_auth.py) for public, authenticated,
and administrator routes in one application.
