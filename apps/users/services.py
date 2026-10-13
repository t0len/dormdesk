from apps.users.constants import Role
from apps.users.models import User


def is_student(user: User) -> bool:
    return bool(getattr(user, "is_authenticated", False) and user.role == Role.STUDENT)


def is_commandant(user: User) -> bool:
    return bool(
        getattr(user, "is_authenticated", False) and user.role == Role.COMMANDANT
    )


def is_security(user: User) -> bool:
    return bool(getattr(user, "is_authenticated", False) and user.role == Role.SECURITY)
