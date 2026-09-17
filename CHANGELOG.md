# Changelog

## Unreleased

## 0.2.0 - 2026-09-17

- Add optional Litestar authentication: `auth_optional` routes accept anonymous requests and
  authenticate a bearer token when one is present, including beneath an `auth_public` router.

## 0.1.0 - 2026-09-17

- Add typed auth principals, role checks, auth-api HTTP verification, and bounded per-process caching.
- Add the optional Litestar plugin with default-deny routes, public-route opt-out, role guards, and no-store responses.
- Add `auth-http` and `litestar` extras.
- Add a runnable Litestar example and artifact checks for the optional integrations.
- Fix positive-result caching, request-level redirect/timeout enforcement, strict bearer parsing,
  and OpenAPI component merging.
- Add `backend_sdk.auth.testing` with a configurable fake authentication client and bearer-header
  helper for consumer service tests.
- Allow `AuthPlugin` to omit HTTP client configuration when an authentication client is injected.
- Add technology badges and an automatically updated coverage badge to the package documentation.
