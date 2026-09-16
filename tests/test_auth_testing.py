import pytest

from backend_sdk.auth import (
    AuthenticationServiceUnavailableError,
    InvalidCredentialsError,
    Principal,
    RoleEnum,
)


@pytest.mark.asyncio
async def test_fake_authentication_client_returns_configured_result() -> None:
    from backend_sdk.auth.testing import FakeAuthenticationClient

    client = FakeAuthenticationClient(
        username="moderator",
        role=RoleEnum.MODERATOR,
        valid_for_seconds=90,
    )

    result = await client.authenticate(token="access-token")  # noqa: S106

    assert result.principal == Principal(username="moderator", role=RoleEnum.MODERATOR)
    assert result.valid_for_seconds == 90


@pytest.mark.asyncio
async def test_fake_authentication_client_tracks_tokens_and_close() -> None:
    from backend_sdk.auth.testing import FakeAuthenticationClient

    client = FakeAuthenticationClient()

    await client.authenticate(token="access-token")  # noqa: S106
    await client.aclose()

    assert client.tokens == ("access-token",)
    assert client.closed is True


@pytest.mark.asyncio
async def test_fake_authentication_client_switches_between_authentication_outcomes() -> None:
    from backend_sdk.auth.testing import FakeAuthenticationClient

    client = FakeAuthenticationClient()

    client.set_invalid_credentials()
    with pytest.raises(InvalidCredentialsError):
        await client.authenticate(token="invalid-token")  # noqa: S106

    client.set_unavailable()
    with pytest.raises(AuthenticationServiceUnavailableError):
        await client.authenticate(token="unavailable-token")  # noqa: S106

    client.set_authenticated(username="owner", role=RoleEnum.OWNER, valid_for_seconds=30)
    result = await client.authenticate(token="valid-token")  # noqa: S106

    assert result.principal == Principal(username="owner", role=RoleEnum.OWNER)
    assert result.valid_for_seconds == 30
    assert client.tokens == ("invalid-token", "unavailable-token", "valid-token")


def test_bearer_headers_builds_authorization_header() -> None:
    from backend_sdk.auth.testing import bearer_headers

    assert bearer_headers(token="opaque-token") == {  # noqa: S106
        "Authorization": "Bearer opaque-token"
    }
