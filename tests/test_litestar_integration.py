import pytest
from litestar import Litestar, Router, get, route
from litestar.connection import Request
from litestar.datastructures import State
from litestar.openapi.config import OpenAPIConfig
from litestar.openapi.spec import Components, SecurityScheme
from litestar.testing import TestClient

from backend_sdk.auth import Principal, RoleEnum
from backend_sdk.auth.http import AuthApiClientConfig
from backend_sdk.auth.testing import FakeAuthenticationClient
from backend_sdk.integrations.litestar import AuthPlugin, RequireRole


def test_plugin_accepts_injected_auth_client_without_http_config() -> None:
    @get("/protected", sync_to_thread=False)
    def protected() -> dict[str, str]:
        return {"status": "ok"}

    app = Litestar(
        route_handlers=[protected],
        plugins=[AuthPlugin(auth_client=FakeAuthenticationClient())],
    )

    with TestClient(app=app) as client:
        assert (
            client.get(
                "/protected",
                headers={"Authorization": "Bearer access-token"},
            ).status_code
            == 200
        )


def test_plugin_requires_http_config_without_injected_auth_client() -> None:
    with pytest.raises(ValueError, match="config is required when auth_client is not provided"):
        AuthPlugin()


def test_plugin_protects_routes_by_default_and_skips_explicitly_public_route() -> None:
    @get("/protected", sync_to_thread=False)
    def protected(request: Request[Principal, object, State]) -> dict[str, str]:
        return {"username": request.user.username}

    @get("/health", opt={"auth_public": True}, sync_to_thread=False)
    def health(request: Request[Principal, object, State]) -> dict[str, str]:
        return {"username": request.user.username}

    auth_client = FakeAuthenticationClient(username="user", role=RoleEnum.USER)
    app = Litestar(
        route_handlers=[protected, health],
        plugins=[
            AuthPlugin(
                config=AuthApiClientConfig(
                    verify_url="https://auth.example.test/api/auth/verify",
                    timeout_seconds=2,
                    cache_ttl_seconds=15,
                    max_cache_entries=10_000,
                ),
                auth_client=auth_client,
            ),
        ],
    )

    with TestClient(app=app) as client:
        assert client.get("/protected").status_code == 401
        protected_response = client.get(
            "/protected",
            headers={"Authorization": "Bearer access-token"},
        )
        assert protected_response.json() == {"username": "user"}
        assert protected_response.headers["cache-control"] == "no-store"
        assert client.get("/health").json() == {"username": "anonymous"}

    assert auth_client.closed is True


def test_role_guard_allows_owner_and_rejects_regular_user() -> None:
    @get("/admin", guards=[RequireRole(RoleEnum.ADMIN)], sync_to_thread=False)
    def admin() -> dict[str, str]:
        return {"status": "ok"}

    auth_client = FakeAuthenticationClient(username="user", role=RoleEnum.USER)
    app = Litestar(
        route_handlers=[admin],
        plugins=[
            AuthPlugin(
                config=AuthApiClientConfig(
                    verify_url="https://auth.example.test/api/auth/verify",
                    timeout_seconds=2,
                    cache_ttl_seconds=15,
                    max_cache_entries=10_000,
                ),
                auth_client=auth_client,
            ),
        ],
    )

    with TestClient(app=app) as client:
        assert (
            client.get("/admin", headers={"Authorization": "Bearer access-token"}).status_code
            == 403
        )
        auth_client.set_authenticated(username="owner", role=RoleEnum.OWNER)
        assert (
            client.get("/admin", headers={"Authorization": "Bearer access-token"}).status_code
            == 200
        )


def test_plugin_bypasses_cors_preflight_with_anonymous_principal() -> None:
    @route("/resource", http_method="OPTIONS", sync_to_thread=False)
    def preflight(request: Request[Principal, object, State]) -> dict[str, str]:
        return {"username": request.user.username}

    auth_client = FakeAuthenticationClient(username="user", role=RoleEnum.USER)
    app = Litestar(
        route_handlers=[preflight],
        plugins=[
            AuthPlugin(
                config=AuthApiClientConfig(
                    verify_url="https://auth.example.test/api/auth/verify",
                    timeout_seconds=2,
                    cache_ttl_seconds=15,
                    max_cache_entries=10_000,
                ),
                auth_client=auth_client,
            ),
        ],
    )

    with TestClient(app=app) as client:
        assert client.options("/resource").json() == {"username": "anonymous"}


def test_public_route_does_not_disable_inherited_role_guard() -> None:
    @get("/status", opt={"auth_public": True}, sync_to_thread=False)
    def status() -> dict[str, str]:
        return {"status": "ok"}

    admin_router = Router(
        path="/admin",
        guards=[RequireRole(RoleEnum.ADMIN)],
        route_handlers=[status],
    )
    auth_client = FakeAuthenticationClient(username="owner", role=RoleEnum.OWNER)
    app = Litestar(
        route_handlers=[admin_router],
        plugins=[
            AuthPlugin(
                config=AuthApiClientConfig(
                    verify_url="https://auth.example.test/api/auth/verify",
                    timeout_seconds=2,
                    cache_ttl_seconds=15,
                    max_cache_entries=10_000,
                ),
                auth_client=auth_client,
            ),
        ],
    )

    with TestClient(app=app) as client:
        assert client.get("/admin/status").status_code == 401


def test_plugin_rejects_malformed_credentials_and_auth_service_outage() -> None:
    @get("/protected", sync_to_thread=False)
    def protected() -> dict[str, str]:
        return {"status": "ok"}

    auth_client = FakeAuthenticationClient(username="user", role=RoleEnum.USER)
    app = Litestar(
        route_handlers=[protected],
        plugins=[
            AuthPlugin(
                config=AuthApiClientConfig(
                    verify_url="https://auth.example.test/api/auth/verify",
                    timeout_seconds=2,
                    cache_ttl_seconds=15,
                    max_cache_entries=10_000,
                ),
                auth_client=auth_client,
            ),
        ],
    )

    with TestClient(app=app) as client:
        assert client.get("/protected", headers={"Authorization": "Basic token"}).status_code == 401
        assert (
            client.get("/protected", headers={b"Authorization": b"Bearer \xe9"}).status_code == 401
        )

        auth_client.set_unavailable()
        assert (
            client.get("/protected", headers={"Authorization": "Bearer token"}).status_code == 503
        )


def test_plugin_adds_bearer_scheme_to_list_components_without_losing_existing_schemes() -> None:
    existing_scheme = SecurityScheme(type="apiKey", name="X-API-Key", security_scheme_in="header")
    auth_client = FakeAuthenticationClient(username="user", role=RoleEnum.USER)

    app = Litestar(
        route_handlers=[],
        openapi_config=OpenAPIConfig(
            title="Example",
            version="1.0.0",
            components=[Components(security_schemes={"apiKey": existing_scheme})],
        ),
        plugins=[
            AuthPlugin(
                config=AuthApiClientConfig(
                    verify_url="https://auth.example.test/api/auth/verify",
                    timeout_seconds=2,
                    cache_ttl_seconds=15,
                    max_cache_entries=10_000,
                ),
                auth_client=auth_client,
            ),
        ],
    )

    openapi_config = app.openapi_config
    assert openapi_config is not None
    assert isinstance(openapi_config.components, list)
    security_schemes = {
        name: scheme
        for components in openapi_config.components
        for name, scheme in (components.security_schemes or {}).items()
    }
    assert security_schemes["apiKey"] is existing_scheme
    assert security_schemes["bearerAuth"] == SecurityScheme(
        type="http",
        scheme="bearer",
        bearer_format="PASETO",
    )


def test_plugin_preserves_existing_bearer_scheme_in_object_components() -> None:
    existing_scheme = SecurityScheme(type="http", scheme="bearer", bearer_format="JWT")
    components = Components(security_schemes={"bearerAuth": existing_scheme})
    auth_client = FakeAuthenticationClient(username="user", role=RoleEnum.USER)

    app = Litestar(
        route_handlers=[],
        openapi_config=OpenAPIConfig(
            title="Example",
            version="1.0.0",
            components=components,
        ),
        plugins=[
            AuthPlugin(
                config=AuthApiClientConfig(
                    verify_url="https://auth.example.test/api/auth/verify",
                    timeout_seconds=2,
                    cache_ttl_seconds=15,
                    max_cache_entries=10_000,
                ),
                auth_client=auth_client,
            ),
        ],
    )

    openapi_config = app.openapi_config
    assert openapi_config is not None
    assert not isinstance(openapi_config.components, list)
    assert openapi_config.components.security_schemes == {"bearerAuth": existing_scheme}
