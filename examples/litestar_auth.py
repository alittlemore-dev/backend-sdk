from litestar import Litestar, Request, Router, get
from litestar.datastructures import State

from backend_sdk.auth import Principal, RoleEnum
from backend_sdk.auth.http import AuthApiClientConfig
from backend_sdk.integrations.litestar import AuthContext, AuthPlugin, RequireRole


@get("/health", opt={"auth_public": True}, sync_to_thread=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


@get("/activity", opt={"auth_optional": True}, sync_to_thread=False)
def activity(request: Request[Principal, AuthContext | None, State]) -> dict[str, str]:
    return {"username": request.user.username, "role": request.user.role}


@get("/me", sync_to_thread=False)
def current_user(request: Request[Principal, AuthContext, State]) -> dict[str, str]:
    return {"username": request.user.username, "role": request.user.role}


@get("/status", sync_to_thread=False)
def admin_status() -> dict[str, str]:
    return {"status": "ok"}


admin_router = Router(
    path="/admin",
    guards=[RequireRole(RoleEnum.ADMIN)],
    route_handlers=[admin_status],
)

app = Litestar(
    route_handlers=[health, activity, current_user, admin_router],
    plugins=[
        AuthPlugin(
            config=AuthApiClientConfig(
                verify_url="http://localhost:8001/api/auth/verify",
                timeout_seconds=2,
                cache_ttl_seconds=15,
                max_cache_entries=10_000,
            ),
        ),
    ],
)
