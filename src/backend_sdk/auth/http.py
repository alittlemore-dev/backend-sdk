import asyncio
import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass

import httpx

from backend_sdk.auth.exceptions import (
    AuthenticationServiceUnavailableError,
    InvalidCredentialsError,
)
from backend_sdk.auth.models import AuthenticationResult, Principal, RoleEnum


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthApiClientConfig:
    verify_url: str
    timeout_seconds: float
    cache_ttl_seconds: float
    max_cache_entries: int

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if self.cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds must not be negative")
        if self.max_cache_entries < 1:
            raise ValueError("max_cache_entries must be greater than zero")


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    result: AuthenticationResult
    expires_at: float


class AuthApiClient:
    def __init__(
        self,
        *,
        config: AuthApiClientConfig,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._http_client = http_client or httpx.AsyncClient(
            timeout=config.timeout_seconds,
            follow_redirects=False,
        )
        self._cache: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._inflight: dict[str, asyncio.Task[AuthenticationResult]] = {}
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._http_client.aclose()

    async def authenticate(self, *, token: str) -> AuthenticationResult:
        cache_key = hashlib.sha256(token.encode()).hexdigest()
        now = time.monotonic()
        async with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None and cached.expires_at > now:
                self._cache.move_to_end(cache_key)
                return cached.result
            if cached is not None:
                del self._cache[cache_key]
            task = self._inflight.get(cache_key)
            if task is None:
                task = asyncio.create_task(
                    self._authenticate_and_cache(token=token, cache_key=cache_key)
                )
                self._inflight[cache_key] = task
        return await asyncio.shield(task)

    async def _authenticate_and_cache(
        self,
        *,
        token: str,
        cache_key: str,
    ) -> AuthenticationResult:
        started_at = time.monotonic()
        try:
            result = await self._authenticate_remote(token=token)
            cache_seconds = min(self._config.cache_ttl_seconds, result.valid_for_seconds)
            if cache_seconds <= 0:
                return result
            async with self._lock:
                self._cache[cache_key] = _CacheEntry(
                    result=result,
                    expires_at=started_at + cache_seconds,
                )
                self._cache.move_to_end(cache_key)
                while len(self._cache) > self._config.max_cache_entries:
                    self._cache.popitem(last=False)
            return result
        finally:
            async with self._lock:
                self._inflight.pop(cache_key, None)

    async def _authenticate_remote(self, *, token: str) -> AuthenticationResult:
        try:
            response = await self._http_client.post(
                self._config.verify_url,
                headers={"Authorization": f"Bearer {token}"},
                follow_redirects=False,
                timeout=self._config.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise AuthenticationServiceUnavailableError from exc
        if response.status_code == 401:
            raise InvalidCredentialsError
        if response.status_code != 200:
            raise AuthenticationServiceUnavailableError
        return self._parse_response(response=response)

    @staticmethod
    def _parse_response(*, response: httpx.Response) -> AuthenticationResult:
        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise AuthenticationServiceUnavailableError from exc
        if not isinstance(payload, dict):
            raise AuthenticationServiceUnavailableError
        username = payload.get("username")
        role_value = payload.get("role")
        valid_for_seconds = payload.get("validForSeconds")
        if (
            not isinstance(username, str)
            or username.strip() == ""
            or not isinstance(role_value, str)
            or not isinstance(valid_for_seconds, int)
            or isinstance(valid_for_seconds, bool)
            or valid_for_seconds <= 0
        ):
            raise AuthenticationServiceUnavailableError
        try:
            role = RoleEnum(role_value)
        except ValueError as exc:
            raise AuthenticationServiceUnavailableError from exc
        if role is RoleEnum.ANON:
            raise AuthenticationServiceUnavailableError
        return AuthenticationResult(
            principal=Principal(username=username, role=role),
            valid_for_seconds=valid_for_seconds,
        )
