from dataclasses import dataclass
from enum import StrEnum


class RoleEnum(StrEnum):
    ANON = "anon"
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"
    OWNER = "owner"


_ROLE_LEVELS = {
    RoleEnum.ANON: 0,
    RoleEnum.USER: 1,
    RoleEnum.MODERATOR: 2,
    RoleEnum.ADMIN: 3,
    RoleEnum.OWNER: 4,
}


@dataclass(frozen=True, slots=True, kw_only=True)
class Principal:
    username: str
    role: RoleEnum

    @classmethod
    def anonymous(cls) -> "Principal":
        return cls(username="anonymous", role=RoleEnum.ANON)

    @property
    def is_anon(self) -> bool:
        return self.role is RoleEnum.ANON

    @property
    def is_owner(self) -> bool:
        return self.role is RoleEnum.OWNER

    @property
    def is_admin(self) -> bool:
        return self.role is RoleEnum.ADMIN

    @property
    def is_moderator(self) -> bool:
        return self.role is RoleEnum.MODERATOR

    @property
    def is_user(self) -> bool:
        return self.role is RoleEnum.USER

    @property
    def can_manage_content(self) -> bool:
        return self.has_role(RoleEnum.MODERATOR)

    @property
    def can_manage_team(self) -> bool:
        return self.has_role(RoleEnum.ADMIN)

    def has_role(self, role: RoleEnum) -> bool:
        return _ROLE_LEVELS[self.role] >= _ROLE_LEVELS[role]


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthenticationResult:
    principal: Principal
    valid_for_seconds: int
