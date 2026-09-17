# Backend SDK

[Русский](https://github.com/alittlemore-dev/backend-sdk/blob/main/.github/README_RU.md)

| Category | Technologies |
|----------|--------------|
| Coverage | ![coverage-backend](./badges/coverage-backend.svg) |
| Runtime | ![python](./badges/python.svg) ![async](./badges/async.svg) ![type-safe](./badges/type-safe.svg) |
| Auth integration | ![litestar](./badges/litestar.svg) ![paseto](./badges/paseto.svg) |
| Testing | ![pytest](./badges/pytest.svg) |
| Quality | ![ruff](./badges/ruff.svg) ![mypy](./badges/mypy.svg) ![bandit](./badges/bandit.svg) ![pip-audit](./badges/pip-audit.svg) |
| Tools | ![uv](./badges/uv.svg) |
| CI/CD | ![github-actions](./badges/github-actions.svg) ![dependabot](./badges/dependabot.svg) |

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
from backend_sdk.auth import Principal, RoleEnum
from backend_sdk.auth.http import AuthApiClientConfig
from backend_sdk.integrations.litestar import AuthContext, AuthPlugin, RequireRole
from litestar import Litestar, Request, get
from litestar.datastructures import State


@get("/health", opt={"auth_public": True})
async def health() -> dict[str, str]:
    return {"status": "ok"}


@get("/activity", opt={"auth_optional": True})
async def activity(
    request: Request[Principal, AuthContext | None, State],
) -> dict[str, str]:
    return {"username": request.user.username}


app = Litestar(
    route_handlers=[health, activity],
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
`opt={"auth_public": True}`. Use `opt={"auth_optional": True}` when a route accepts
anonymous requests but should authenticate a bearer token when one is present; this also
overrides an inherited `auth_public` option. Malformed or invalid supplied credentials still
return 401, and an unavailable verifier returns 503. Protect privileged routes with
`RequireRole(RoleEnum.ADMIN)`. Successful checks are cached in each process for at most 15
seconds; set `cache_ttl_seconds=0` to disable this. Services must still enforce resource
ownership in their own domain logic.

The cache is intentionally process-local: it is a short availability and latency
optimization, adds no infrastructure dependency, and never becomes an authorization
source of truth. Each process can perform one auth-api request per token and TTL.

See [`examples/litestar_auth.py`](../examples/litestar_auth.py) for public, authenticated,
and administrator routes in one application.
