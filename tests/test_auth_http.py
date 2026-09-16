import asyncio

import httpx
import pytest

from backend_sdk.auth import RoleEnum
from backend_sdk.auth.exceptions import (
    AuthenticationServiceUnavailableError,
    InvalidCredentialsError,
)
from backend_sdk.auth.http import AuthApiClient, AuthApiClientConfig


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        (
            {"timeout_seconds": 0, "cache_ttl_seconds": 15, "max_cache_entries": 1},
            "timeout_seconds",
        ),
        (
            {"timeout_seconds": 2, "cache_ttl_seconds": -1, "max_cache_entries": 1},
            "cache_ttl_seconds",
        ),
        (
            {"timeout_seconds": 2, "cache_ttl_seconds": 15, "max_cache_entries": 0},
            "max_cache_entries",
        ),
    ],
)
def test_client_config_rejects_invalid_cache_and_timeout_settings(
    kwargs: dict[str, int],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        AuthApiClientConfig(verify_url="https://auth.example.test/verify", **kwargs)


@pytest.mark.asyncio
async def test_authenticate_uses_verified_auth_api_response_and_caches_it() -> None:
    requests: list[httpx.Request] = []

    async def verify(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"username": "editor", "role": "moderator", "validForSeconds": 60},
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(verify))
    client = AuthApiClient(
        config=AuthApiClientConfig(
            verify_url="https://auth.example.test/api/auth/verify",
            timeout_seconds=2,
            cache_ttl_seconds=15,
            max_cache_entries=10_000,
        ),
        http_client=http_client,
    )

    first = await client.authenticate(token="access-token")  # noqa: S106
    second = await client.authenticate(token="access-token")  # noqa: S106

    assert first.principal.username == "editor"
    assert first.principal.role is RoleEnum.MODERATOR
    assert first.valid_for_seconds == 60
    assert second == first
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].headers["Authorization"] == "Bearer access-token"
    await client.aclose()


@pytest.mark.asyncio
async def test_authenticate_does_not_cache_when_cache_is_disabled() -> None:
    requests: list[httpx.Request] = []

    async def verify(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"username": "user", "role": "user", "validForSeconds": 60},
        )

    client = AuthApiClient(
        config=AuthApiClientConfig(
            verify_url="https://auth.example.test/api/auth/verify",
            timeout_seconds=2,
            cache_ttl_seconds=0,
            max_cache_entries=10_000,
        ),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(verify)),
    )

    await client.authenticate(token="access-token")  # noqa: S106
    await client.authenticate(token="access-token")  # noqa: S106

    assert len(requests) == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_authenticate_limits_cache_lifetime_from_request_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_time = 100.0
    requests: list[httpx.Request] = []

    def monotonic() -> float:
        return current_time

    async def verify(request: httpx.Request) -> httpx.Response:
        nonlocal current_time
        requests.append(request)
        current_time = 101.0
        return httpx.Response(
            200,
            json={"username": "user", "role": "user", "validForSeconds": 2},
        )

    monkeypatch.setattr("backend_sdk.auth.http.time.monotonic", monotonic)
    client = AuthApiClient(
        config=AuthApiClientConfig(
            verify_url="https://auth.example.test/api/auth/verify",
            timeout_seconds=2,
            cache_ttl_seconds=15,
            max_cache_entries=10_000,
        ),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(verify)),
    )

    await client.authenticate(token="access-token")  # noqa: S106
    await client.authenticate(token="access-token")  # noqa: S106
    current_time = 102.0
    await client.authenticate(token="access-token")  # noqa: S106

    assert len(requests) == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_authenticate_observes_revocation_after_cache_expiry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_time = 100.0
    revoked = False
    requests: list[httpx.Request] = []

    async def verify(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if revoked:
            return httpx.Response(401)
        return httpx.Response(
            200,
            json={"username": "user", "role": "user", "validForSeconds": 60},
        )

    monkeypatch.setattr("backend_sdk.auth.http.time.monotonic", lambda: current_time)
    client = AuthApiClient(
        config=AuthApiClientConfig(
            verify_url="https://auth.example.test/api/auth/verify",
            timeout_seconds=2,
            cache_ttl_seconds=15,
            max_cache_entries=10_000,
        ),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(verify)),
    )

    cached_result = await client.authenticate(token="access-token")  # noqa: S106
    revoked = True
    assert await client.authenticate(token="access-token") == cached_result  # noqa: S106
    current_time = 115.0
    with pytest.raises(InvalidCredentialsError):
        await client.authenticate(token="access-token")  # noqa: S106

    assert len(requests) == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_authenticate_evicts_expired_and_oldest_cache_entries() -> None:
    requests: list[httpx.Request] = []

    async def verify(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "username": request.headers["Authorization"],
                "role": "user",
                "validForSeconds": 60,
            },
        )

    client = AuthApiClient(
        config=AuthApiClientConfig(
            verify_url="https://auth.example.test/api/auth/verify",
            timeout_seconds=2,
            cache_ttl_seconds=15,
            max_cache_entries=1,
        ),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(verify)),
    )

    await client.authenticate(token="first-token")  # noqa: S106
    await client.authenticate(token="second-token")  # noqa: S106
    await client.authenticate(token="first-token")  # noqa: S106

    assert len(requests) == 3
    await client.aclose()


@pytest.mark.asyncio
async def test_authenticate_combines_concurrent_checks_for_the_same_token() -> None:
    request_started = asyncio.Event()
    finish_request = asyncio.Event()
    requests: list[httpx.Request] = []

    async def verify(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        request_started.set()
        await finish_request.wait()
        return httpx.Response(
            200,
            json={"username": "user", "role": "user", "validForSeconds": 60},
        )

    client = AuthApiClient(
        config=AuthApiClientConfig(
            verify_url="https://auth.example.test/api/auth/verify",
            timeout_seconds=2,
            cache_ttl_seconds=15,
            max_cache_entries=10_000,
        ),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(verify)),
    )

    first = asyncio.create_task(client.authenticate(token="access-token"))  # noqa: S106
    second = asyncio.create_task(client.authenticate(token="access-token"))  # noqa: S106
    await request_started.wait()
    finish_request.set()

    first_result, second_result = await asyncio.gather(first, second)
    assert first_result == second_result
    assert len(requests) == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_authenticate_disables_redirects_and_applies_configured_timeout() -> None:
    requests: list[httpx.Request] = []

    async def redirect(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(307, headers={"Location": "https://untrusted.example.test/verify"})

    client = AuthApiClient(
        config=AuthApiClientConfig(
            verify_url="https://auth.example.test/api/auth/verify",
            timeout_seconds=2,
            cache_ttl_seconds=15,
            max_cache_entries=10_000,
        ),
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(redirect),
            follow_redirects=True,
            timeout=99,
        ),
    )

    with pytest.raises(AuthenticationServiceUnavailableError):
        await client.authenticate(token="access-token")  # noqa: S106

    assert len(requests) == 1
    assert requests[0].url.host == "auth.example.test"
    assert requests[0].extensions["timeout"] == {
        "connect": 2,
        "read": 2,
        "write": 2,
        "pool": 2,
    }
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 503])
async def test_authenticate_does_not_cache_failed_checks(status_code: int) -> None:
    requests: list[httpx.Request] = []

    async def reject(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status_code)

    client = AuthApiClient(
        config=AuthApiClientConfig(
            verify_url="https://auth.example.test/api/auth/verify",
            timeout_seconds=2,
            cache_ttl_seconds=15,
            max_cache_entries=10_000,
        ),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(reject)),
    )
    expected_error = (
        InvalidCredentialsError if status_code == 401 else AuthenticationServiceUnavailableError
    )

    for _ in range(2):
        with pytest.raises(expected_error):
            await client.authenticate(token="access-token")  # noqa: S106

    assert len(requests) == 2
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "payload", "error"),
    [
        (401, {}, InvalidCredentialsError),
        (503, {}, AuthenticationServiceUnavailableError),
        (
            200,
            {"username": "", "role": "user", "validForSeconds": 1},
            AuthenticationServiceUnavailableError,
        ),
        (
            200,
            {"username": "user", "role": "anon", "validForSeconds": 1},
            AuthenticationServiceUnavailableError,
        ),
        (
            200,
            {"username": "user", "role": "unknown", "validForSeconds": 1},
            AuthenticationServiceUnavailableError,
        ),
    ],
)
async def test_authenticate_rejects_invalid_and_unavailable_auth_api_responses(
    status_code: int,
    payload: dict[str, object],
    error: type[Exception],
) -> None:
    async def verify(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    client = AuthApiClient(
        config=AuthApiClientConfig(
            verify_url="https://auth.example.test/api/auth/verify",
            timeout_seconds=2,
            cache_ttl_seconds=15,
            max_cache_entries=1,
        ),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(verify)),
    )

    with pytest.raises(error):
        await client.authenticate(token="access-token")  # noqa: S106
    await client.aclose()


@pytest.mark.asyncio
async def test_authenticate_converts_transport_and_malformed_payload_failures_to_unavailable() -> (
    None
):
    async def transport_failure(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unavailable")

    client = AuthApiClient(
        config=AuthApiClientConfig(
            verify_url="https://auth.example.test/api/auth/verify",
            timeout_seconds=2,
            cache_ttl_seconds=15,
            max_cache_entries=1,
        ),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(transport_failure)),
    )

    with pytest.raises(AuthenticationServiceUnavailableError):
        await client.authenticate(token="access-token")  # noqa: S106
    await client.aclose()

    for response in (
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, json=["not", "an", "object"]),
    ):

        async def malformed(
            _: httpx.Request,
            response: httpx.Response = response,
        ) -> httpx.Response:
            return response

        client = AuthApiClient(
            config=AuthApiClientConfig(
                verify_url="https://auth.example.test/api/auth/verify",
                timeout_seconds=2,
                cache_ttl_seconds=15,
                max_cache_entries=1,
            ),
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(malformed)),
        )
        with pytest.raises(AuthenticationServiceUnavailableError):
            await client.authenticate(token="access-token")  # noqa: S106
        await client.aclose()
