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
    CredentialTypeEnum,
    InvalidCredentialsError,
    Principal,
    RoleEnum,
)
from backend_sdk.auth.http import AuthApiClient, AuthApiClientConfig

__all__ = ["AuthContext", "AuthPlugin", "RequireRole", "authorize_pat_route"]


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthContext:
    valid_for_seconds: int
    credential_type: CredentialTypeEnum = CredentialTypeEnum.SESSION
    credential_id: str = ""
    permissions: frozenset[str] = frozenset()
    cache_ttl_seconds: int = 0

    @property
    def is_pat(self) -> bool:
        return self.credential_type is CredentialTypeEnum.PAT

    def allows_permissions(self, *permissions: str) -> bool:
        return not self.is_pat or set(permissions).issubset(self.permissions)

    def require_permissions(self, *permissions: str) -> None:
        if not self.allows_permissions(*permissions):
            raise PermissionDeniedException


def authorize_pat_route(context: AuthContext, handler: BaseRouteHandler) -> None:
    if not context.is_pat:
        return
    permissions = handler.opt.get("pat_permissions")
    if (
        handler.opt.get("pat_session_only") is True
        or not isinstance(permissions, tuple | list)
        or not permissions
        or any(not isinstance(value, str) or not value for value in permissions)
    ):
        raise PermissionDeniedException
    context.require_permissions(*permissions)


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
        route_handler = scope.get("route_handler")
        if (
            scope["type"] == ScopeType.HTTP
            and route_handler is not None
            and route_handler.opt.get("auth_optional") is True
        ):
            connection = ASGIConnection[Any, Any, Any, Any](scope)
            if connection.headers.get("Authorization") is not None:
                auth_result = await self.authenticate_request(connection)
                scope["user"] = auth_result.user
                scope["auth"] = auth_result.auth
            await self.app(scope, receive, send)
            return
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
        context = AuthContext(
            valid_for_seconds=result.valid_for_seconds,
            credential_type=result.credential_type,
            credential_id=result.credential_id,
            permissions=result.permissions,
            cache_ttl_seconds=result.cache_ttl_seconds,
        )
        authorize_pat_route(context, connection.route_handler)
        return LitestarAuthenticationResult(user=result.principal, auth=context)

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
    return SecurityScheme(
        type="http", scheme="bearer", bearer_format="PASETO or personal API token"
    )


async def _set_private_cache_control(message: Message, scope: Scope) -> None:
    if message["type"] != "http.response.start":
        return
    user = scope.get("user")
    if not isinstance(user, Principal) or user.is_anon:
        return
    MutableScopeHeaders.from_message(message)["Cache-Control"] = "no-store"
