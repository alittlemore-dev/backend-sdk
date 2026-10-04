import asyncio

import httpx
import pytest
from litestar import Litestar, get
from litestar.testing import TestClient

from backend_sdk.auth import AuthenticationResult, CredentialTypeEnum, Principal, RoleEnum
from backend_sdk.auth.exceptions import (
    AuthenticationServiceUnavailableError,
    InvalidCredentialsError,
)
from backend_sdk.auth.http import AuthApiClient, AuthApiClientConfig
from backend_sdk.auth.testing import FakeAuthenticationClient
from backend_sdk.integrations.litestar import AuthContext, AuthPlugin


def verification(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "username": "owner",
        "role": "owner",
        "validForSeconds": 3600,
        "credentialType": "pat",
        "credentialId": "personal-token-id",
        "permissions": ["workspace.resumes.read"],
        "cacheTtlSeconds": 0,
    }
    return payload | changes


def config() -> AuthApiClientConfig:
    return AuthApiClientConfig(
        verify_url="https://auth.example.test/api/auth/verify/v2",
        timeout_seconds=2,
        cache_ttl_seconds=60,
        max_cache_entries=100,
    )


@pytest.mark.asyncio
async def test_pat_is_reverified_after_revocation_without_cache() -> None:
    revoked = False
    requests = 0

    def verify(_: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(401) if revoked else httpx.Response(200, json=verification())

    client = AuthApiClient(
        config=config(), http_client=httpx.AsyncClient(transport=httpx.MockTransport(verify))
    )
    result = await client.authenticate(token="alm_pat_test")  # noqa: S106
    assert result.credential_type is CredentialTypeEnum.PAT
    assert result.permissions == frozenset({"workspace.resumes.read"})
    assert result.credential_id == "personal-token-id"
    revoked = True
    with pytest.raises(InvalidCredentialsError):
        await client.authenticate(token="alm_pat_test")  # noqa: S106
    assert requests == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_new_pat_request_does_not_join_an_older_verification() -> None:
    started = asyncio.Event()
    finish = asyncio.Event()
    requests = 0

    async def verify(_: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests == 1:
            started.set()
            await finish.wait()
            return httpx.Response(200, json=verification())
        return httpx.Response(401)

    client = AuthApiClient(
        config=config(), http_client=httpx.AsyncClient(transport=httpx.MockTransport(verify))
    )
    first = asyncio.create_task(client.authenticate(token="alm_pat_test"))  # noqa: S106
    await started.wait()
    try:
        with pytest.raises(InvalidCredentialsError):
            await asyncio.wait_for(client.authenticate(token="alm_pat_test"), timeout=1)  # noqa: S106
    finally:
        finish.set()
        await first
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"credentialType": "unknown"},
        {"credentialId": ""},
        {"permissions": "all"},
        {"permissions": [1]},
        {"permissions": [""]},
        {"cacheTtlSeconds": 1},
        {"cacheTtlSeconds": True},
        {"cacheTtlSeconds": -1},
    ],
)
async def test_invalid_v2_credentials_fail_closed(changes: dict[str, object]) -> None:
    client = AuthApiClient(
        config=config(),
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json=verification(**changes)),
            )
        ),
    )
    with pytest.raises(AuthenticationServiceUnavailableError):
        await client.authenticate(token="alm_pat_test")  # noqa: S106
    await client.aclose()


@pytest.mark.asyncio
async def test_v2_does_not_interpret_a_legacy_response_as_full_session_access() -> None:
    client = AuthApiClient(
        config=config(),
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200, json={"username": "owner", "role": "owner", "validForSeconds": 60}
                ),
            )
        ),
    )
    with pytest.raises(AuthenticationServiceUnavailableError):
        await client.authenticate(token="opaque-token")  # noqa: S106
    await client.aclose()


@pytest.mark.parametrize(
    ("granted", "required", "expected"),
    [
        (["workspace.resumes.read"], ("workspace.resumes.read",), 200),
        ([], ("workspace.resumes.read",), 403),
        (["workspace.resumes.read"], None, 403),
        (["workspace.resumes.read"], (), 403),
    ],
)
def test_pat_route_is_explicitly_allowlisted(
    granted: list[str], required: tuple[str, ...] | None, expected: int
) -> None:
    options = {} if required is None else {"pat_permissions": required}

    @get("/resumes", opt=options, sync_to_thread=False)
    def resumes() -> dict[str, str]:
        return {"status": "ok"}

    auth_client = FakeAuthenticationClient()
    auth_client.set_result(
        AuthenticationResult(
            principal=Principal(username="owner", role=RoleEnum.OWNER),
            valid_for_seconds=3600,
            credential_type=CredentialTypeEnum.PAT,
            credential_id="pat-id",
            permissions=frozenset(granted),
            cache_ttl_seconds=0,
        )
    )
    app = Litestar(route_handlers=[resumes], plugins=[AuthPlugin(auth_client=auth_client)])
    with TestClient(app=app) as client:
        assert (
            client.get("/resumes", headers={"Authorization": "Bearer alm_pat_test"}).status_code
            == expected
        )


def test_session_only_route_rejects_pat_even_with_matching_scope() -> None:
    @get(
        "/tokens",
        opt={"pat_session_only": True, "pat_permissions": ("auth.account.read",)},
        sync_to_thread=False,
    )
    def tokens() -> dict[str, str]:
        return {"status": "ok"}

    auth_client = FakeAuthenticationClient()
    auth_client.set_result(
        AuthenticationResult(
            principal=Principal(username="owner", role=RoleEnum.OWNER),
            valid_for_seconds=3600,
            credential_type=CredentialTypeEnum.PAT,
            credential_id="pat-id",
            permissions=frozenset({"auth.account.read"}),
            cache_ttl_seconds=0,
        )
    )
    app = Litestar(route_handlers=[tokens], plugins=[AuthPlugin(auth_client=auth_client)])
    with TestClient(app=app) as client:
        assert (
            client.get("/tokens", headers={"Authorization": "Bearer alm_pat_test"}).status_code
            == 403
        )


def test_pat_context_requires_all_permissions_and_sessions_keep_role_flow() -> None:
    context = AuthContext(
        valid_for_seconds=60,
        credential_type=CredentialTypeEnum.PAT,
        credential_id="pat-id",
        permissions=frozenset({"read"}),
        cache_ttl_seconds=0,
    )
    assert context.is_pat
    context.require_permissions("read")
    from litestar.exceptions import PermissionDeniedException

    with pytest.raises(PermissionDeniedException):
        context.require_permissions("read", "publish")
    AuthContext(valid_for_seconds=60).require_permissions("publish")
