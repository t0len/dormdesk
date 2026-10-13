from django.db import models

MIN_COURSE = 1
MAX_COURSE = 4


class Role(models.TextChoices):
    STUDENT = "student", "Студент"
    COMMANDANT = "commandant", "Комендант"
    SECURITY = "security", "Охрана"


STAFF_ROLES = frozenset({Role.COMMANDANT, Role.SECURITY})
