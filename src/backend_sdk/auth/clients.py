from typing import Protocol

from backend_sdk.auth.models import AuthenticationResult


class AuthenticationClient(Protocol):
    async def authenticate(self, *, token: str) -> AuthenticationResult: ...

    async def aclose(self) -> None: ...
