# Authentication v2 and personal API tokens

Version 0.3.0 adds credential context to the existing session authentication contract.
Configure `AuthClientConfig.verify_url` with the auth service's `/api/auth/verify/v2` endpoint.
Internal consumers use the service URL; external callers use the site's public HTTPS API.

A successful verification returns `username`, the current `role`, `validForSeconds`,
`credentialType` (`session` or `pat`), `credentialId`, `permissions`, and `cacheTtlSeconds`.
The legacy `/api/auth/verify` endpoint accepts browser session access tokens only.
The SDK still accepts its legacy response when explicitly configured with the legacy URL.

PAT values start with `alm_pat_`. Every PAT request performs a fresh verification: neither
positive caches nor shared in-flight verification requests are used. The SDK rejects a v2 PAT
response whose cache TTL is nonzero. After a completed revocation, the next request fails;
a request whose authentication already completed may finish.

## Litestar route policy

Every protected PAT-capable handler declares a nonempty concrete permission set:

```python
@get("/resumes", opt={"pat_permissions": ("workspace.resumes.read",)})
async def list_resumes(...) -> ResumeList:
    ...
```

All declared permissions are required. Use `opt={"pat_session_only": True}` for operations
reserved to browser sessions. A protected handler without an explicit PAT permission policy
rejects PATs. These policies do not alter ordinary session behavior or grant a role: existing
`RequireRole` guards and object-owner filters remain necessary.

`request.auth` is an `AuthContext` containing `credential_type`, `credential_id`, and
`permissions`, with `is_pat`, `allows_permissions(...)`, and `require_permissions(...)`.
For state-dependent operations, check the publication permission after loading/locking the
current object and before changing published content. Static route permissions alone cannot
express this condition.

Anonymous routes retain `auth_public`; optional authentication retains `auth_optional`.
Internal service credentials and webhook validation are independent of PAT authentication.

## Release boundary

Build and verify the SDK with `make quality` and `make build`. Publish 0.3.0 as a separate
release before updating production consumer dependencies and lockfiles. Local consumer Make
checks accept an absolute `LOCAL_BACKEND_SDK_WHEEL` path and install that built artifact without
publishing it. The integrated local `infra make dev` builds the SDK and overlays its wheel in
local images; production image definitions and registry dependencies are unaffected.
