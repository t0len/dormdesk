from typing import Any

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.abstracts.models import TimeStampedModel
from apps.users.constants import MAX_COURSE, MIN_COURSE, STAFF_ROLES, Role


class UserManager(BaseUserManager["User"]):
    def create_user(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        if not email:
            raise ValueError("Нужно указать email.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", Role.COMMANDANT)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Суперпользователь должен иметь is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Суперпользователь должен иметь is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    email = models.EmailField("email", unique=True)
    first_name = models.CharField("имя", max_length=150)
    last_name = models.CharField("фамилия", max_length=150)
    phone = models.CharField("телефон", max_length=20)
    role = models.CharField(
        "роль",
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
    )
    is_active = models.BooleanField("активен", default=True)
    is_staff = models.BooleanField("доступ в админку", default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name", "phone"]

    class Meta:
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"
        ordering = ["email"]

    def __str__(self) -> str:
        return f"{self.last_name} {self.first_name} ({self.email})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.role in STAFF_ROLES:
            self.is_staff = True
        elif not self.is_superuser:
            self.is_staff = False
        super().save(*args, **kwargs)

    def has_perm(self, perm: str, obj: Any | None = None) -> bool:
        if self.is_active and self.role in STAFF_ROLES:
            return True
        return super().has_perm(perm, obj)

    def has_module_perms(self, app_label: str) -> bool:
        if self.is_active and self.role in STAFF_ROLES:
            return True
        return super().has_module_perms(app_label)


class StudentProfile(TimeStampedModel):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="student_profile",
        verbose_name="пользователь",
    )
    student_number = models.CharField("номер студенческого", max_length=32, unique=True)
    faculty = models.CharField("факультет", max_length=128)
    group = models.CharField("группа", max_length=32)
    course = models.PositiveSmallIntegerField(
        "курс",
        validators=[MinValueValidator(MIN_COURSE), MaxValueValidator(MAX_COURSE)],
    )

    class Meta:
        verbose_name = "профиль студента"
        verbose_name_plural = "профили студентов"

    def __str__(self) -> str:
        return f"{self.student_number} — {self.user.last_name}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        if self.user_id and self.user.role != Role.STUDENT:
            raise ValidationError(
                "Профиль студента только у пользователя с ролью «студент»."
            )
        if self.course is not None and not MIN_COURSE <= self.course <= MAX_COURSE:
            raise ValidationError(
                {"course": f"Курс должен быть от {MIN_COURSE} до {MAX_COURSE}."}
            )
