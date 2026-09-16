from backend_sdk.auth.exceptions import (
    AuthenticationServiceUnavailableError,
    InvalidCredentialsError,
)
from backend_sdk.auth.models import AuthenticationResult, Principal, RoleEnum

__all__ = ["FakeAuthenticationClient", "bearer_headers"]


class FakeAuthenticationClient:
    def __init__(
        self,
        *,
        username: str = "test-user",
        role: RoleEnum = RoleEnum.USER,
        valid_for_seconds: int = 60,
    ) -> None:
        self._result = AuthenticationResult(
            principal=Principal(username=username, role=role),
            valid_for_seconds=valid_for_seconds,
        )
        self._error_type: type[Exception] | None = None
        self._tokens: list[str] = []
        self._closed = False

    @property
    def tokens(self) -> tuple[str, ...]:
        return tuple(self._tokens)

    @property
    def closed(self) -> bool:
        return self._closed

    def set_authenticated(
        self,
        *,
        username: str = "test-user",
        role: RoleEnum = RoleEnum.USER,
        valid_for_seconds: int = 60,
    ) -> None:
        self._result = AuthenticationResult(
            principal=Principal(username=username, role=role),
            valid_for_seconds=valid_for_seconds,
        )
        self._error_type = None

    def set_invalid_credentials(self) -> None:
        self._error_type = InvalidCredentialsError

    def set_unavailable(self) -> None:
        self._error_type = AuthenticationServiceUnavailableError

    async def authenticate(self, *, token: str) -> AuthenticationResult:
        self._tokens.append(token)
        if self._error_type is not None:
            raise self._error_type
        return self._result

    async def aclose(self) -> None:
        self._closed = True


def bearer_headers(*, token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
