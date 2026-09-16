from dataclasses import dataclass
from typing import Any

from litestar import Litestar
from litestar.config.app import AppConfig
from litestar.connection import ASGIConnection
from litestar.datastructures import MutableScopeHeaders
from litestar.enums import ScopeType
from litestar.exceptions import (
    NotAuthorizedException,
    PermissionDeniedException,
    ServiceUnavailableException,
)
from litestar.handlers import BaseRouteHandler
from litestar.middleware import AbstractAuthenticationMiddleware
from litestar.middleware import AuthenticationResult as LitestarAuthenticationResult
from litestar.middleware.base import DefineMiddleware
from litestar.openapi.spec import Components, SecurityScheme
from litestar.plugins import InitPlugin
from litestar.types import ASGIApp, Message, Receive, Scope, Send

from backend_sdk.auth import (
    AuthenticationClient,
    AuthenticationServiceUnavailableError,
    InvalidCredentialsError,
    Principal,
    RoleEnum,
)
from backend_sdk.auth.http import AuthApiClient, AuthApiClientConfig

__all__ = ["AuthContext", "AuthPlugin", "RequireRole"]


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthContext:
    valid_for_seconds: int


class AuthMiddleware(AbstractAuthenticationMiddleware):
    def __init__(self, app: ASGIApp, client: AuthenticationClient) -> None:
        super().__init__(
            app=app,
            exclude=None,
            exclude_from_auth_key="auth_public",
            exclude_http_methods=None,
            scopes={ScopeType.HTTP},
        )
        self._client = client

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope["user"] = Principal.anonymous()
        scope["auth"] = None
        await super().__call__(scope, receive, send)

    async def authenticate_request(
        self,
        connection: ASGIConnection[Any, Any, Any, Any],
    ) -> LitestarAuthenticationResult:
        token = self._read_bearer_token(connection=connection)
        try:
            result = await self._client.authenticate(token=token)
        except InvalidCredentialsError as exc:
            raise NotAuthorizedException from exc
        except AuthenticationServiceUnavailableError as exc:
            raise ServiceUnavailableException from exc
        return LitestarAuthenticationResult(
            user=result.principal,
            auth=AuthContext(valid_for_seconds=result.valid_for_seconds),
        )

    @staticmethod
    def _read_bearer_token(*, connection: ASGIConnection[Any, Any, Any, Any]) -> str:
        authorization = connection.headers.get("Authorization")
        if authorization is None:
            raise NotAuthorizedException
        scheme, separator, token = authorization.partition(" ")
        if (
            scheme != "Bearer"
            or separator == ""
            or token == ""  # nosec B105
            or token != token.strip()
            or " " in token
            or not token.isascii()
            or not token.isprintable()
        ):
            raise NotAuthorizedException
        return token


@dataclass(frozen=True, slots=True)
class RequireRole:
    role: RoleEnum

    def __call__(
        self,
        connection: ASGIConnection[Any, Any, Any, Any],
        _: BaseRouteHandler,
    ) -> None:
        user = connection.user
        if not isinstance(user, Principal) or user.is_anon:
            raise NotAuthorizedException
        if not user.has_role(self.role):
            raise PermissionDeniedException


class AuthPlugin(InitPlugin):
    def __init__(
        self,
        *,
        config: AuthApiClientConfig | None = None,
        auth_client: AuthenticationClient | None = None,
    ) -> None:
        if auth_client is not None:
            self._client = auth_client
            return
        if config is None:
            raise ValueError("config is required when auth_client is not provided")
        self._client = AuthApiClient(config=config)

    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        app_config.middleware.append(DefineMiddleware(AuthMiddleware, client=self._client))
        app_config.before_send.append(_set_private_cache_control)
        app_config.on_shutdown.append(self._close_client)
        if app_config.openapi_config is None:
            return app_config
        _add_bearer_auth_scheme(components=app_config.openapi_config.components)
        return app_config

    async def _close_client(self, _: Litestar) -> None:
        await self._client.aclose()


def _add_bearer_auth_scheme(*, components: Components | list[Components]) -> None:
    if isinstance(components, list):
        if any("bearerAuth" in (item.security_schemes or {}) for item in components):
            return
        components.append(Components(security_schemes={"bearerAuth": _bearer_auth_scheme()}))
        return
    if components.security_schemes is None:
        components.security_schemes = {}
    components.security_schemes.setdefault("bearerAuth", _bearer_auth_scheme())


def _bearer_auth_scheme() -> SecurityScheme:
    return SecurityScheme(type="http", scheme="bearer", bearer_format="PASETO")


async def _set_private_cache_control(message: Message, scope: Scope) -> None:
    if message["type"] != "http.response.start":
        return
    user = scope.get("user")
    if not isinstance(user, Principal) or user.is_anon:
        return
    MutableScopeHeaders.from_message(message)["Cache-Control"] = "no-store"
