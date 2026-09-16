import pytest

import backend_sdk


def test_owner_inherits_admin_and_moderator_permissions() -> None:
    principal = backend_sdk.Principal(
        username="owner",
        role=backend_sdk.RoleEnum.OWNER,
    )

    assert principal.is_owner is True
    assert principal.is_admin is False
    assert principal.can_manage_team is True
    assert principal.can_manage_content is True
    assert principal.has_role(backend_sdk.RoleEnum.ADMIN) is True
    assert principal.has_role(backend_sdk.RoleEnum.MODERATOR) is True
    assert principal.has_role(backend_sdk.RoleEnum.USER) is True


def test_anonymous_principal_has_no_privileged_permissions() -> None:
    principal = backend_sdk.Principal.anonymous()

    assert principal.username == "anonymous"
    assert principal.is_anon is True
    assert principal.can_manage_team is False
    assert principal.can_manage_content is False
    assert principal.has_role(backend_sdk.RoleEnum.USER) is False


@pytest.mark.parametrize(
    ("role", "is_moderator", "is_user"),
    [
        (backend_sdk.RoleEnum.MODERATOR, True, False),
        (backend_sdk.RoleEnum.USER, False, True),
    ],
)
def test_principal_exposes_exact_role_properties(
    role: backend_sdk.RoleEnum,
    is_moderator: bool,
    is_user: bool,
) -> None:
    principal = backend_sdk.Principal(username="member", role=role)

    assert principal.is_moderator is is_moderator
    assert principal.is_user is is_user
