from typing import Any

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, ReadOnlyPasswordHashField
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest

from apps.users.constants import MAX_COURSE, MIN_COURSE, Role
from apps.users.models import StudentProfile, User


class EmailAuthenticationForm(AuthenticationForm):
    def __init__(
        self,
        request: HttpRequest | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(request, *args, **kwargs)
        self.fields["username"].label = "Email"


class StudentRegistrationForm(forms.Form):
    email = forms.EmailField(label="Email")
    first_name = forms.CharField(label="Имя", max_length=150)
    last_name = forms.CharField(label="Фамилия", max_length=150)
    phone = forms.CharField(label="Телефон", max_length=20)
    password1 = forms.CharField(label="Пароль", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Повтор пароля", widget=forms.PasswordInput)
    student_number = forms.CharField(label="Номер студенческого", max_length=32)
    faculty = forms.CharField(label="Факультет", max_length=128)
    group = forms.CharField(label="Группа", max_length=32)
    course = forms.IntegerField(
        label="Курс",
        min_value=MIN_COURSE,
        max_value=MAX_COURSE,
    )

    def clean_email(self) -> str:
        email = User.objects.normalize_email(self.cleaned_data["email"])
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Пользователь с таким email уже есть.")
        return email

    def clean_student_number(self) -> str:
        student_number = self.cleaned_data["student_number"].strip()
        if StudentProfile.objects.filter(student_number=student_number).exists():
            raise ValidationError("Такой номер студенческого уже зарегистрирован.")
        return student_number

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        if cleaned_data is None:
            return {}
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Пароли не совпадают.")
        if password1 and password2 and password1 == password2:
            try:
                password_validation.validate_password(password2)
            except ValidationError as exc:
                self.add_error("password2", exc)
        return cleaned_data

    @transaction.atomic
    def save(self) -> User:
        user = User.objects.create_user(
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            phone=self.cleaned_data["phone"],
            role=Role.STUDENT,
        )
        StudentProfile.objects.create(
            user=user,
            student_number=self.cleaned_data["student_number"],
            faculty=self.cleaned_data["faculty"],
            group=self.cleaned_data["group"],
            course=self.cleaned_data["course"],
        )
        return user


class ProfileUpdateForm(forms.Form):
    phone = forms.CharField(label="Телефон", max_length=20)
    group = forms.CharField(label="Группа", max_length=32)
    course = forms.IntegerField(
        label="Курс",
        min_value=MIN_COURSE,
        max_value=MAX_COURSE,
    )

    def __init__(self, user: User, *args: Any, **kwargs: Any) -> None:
        self.user = user
        profile = user.student_profile
        super().__init__(*args, **kwargs)
        self.fields["phone"].initial = user.phone
        self.fields["group"].initial = profile.group
        self.fields["course"].initial = profile.course

    def save(self) -> User:
        self.user.phone = self.cleaned_data["phone"]
        self.user.save(update_fields=["phone", "updated_at"])
        profile = self.user.student_profile
        profile.group = self.cleaned_data["group"]
        profile.course = self.cleaned_data["course"]
        profile.save(update_fields=["group", "course", "updated_at"])
        return self.user


class StaffProfileForm(forms.Form):
    phone = forms.CharField(label="Телефон", max_length=20)

    def __init__(self, user: User, *args: Any, **kwargs: Any) -> None:
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["phone"].initial = user.phone

    def save(self) -> User:
        self.user.phone = self.cleaned_data["phone"]
        self.user.save(update_fields=["phone", "updated_at"])
        return self.user


class AdminUserCreationForm(forms.ModelForm):
    password1 = forms.CharField(label="Пароль", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Повтор пароля", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "phone", "role")

    def clean_password2(self) -> str:
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Пароли не совпадают.")
        if password2:
            password_validation.validate_password(password2, self.instance)
        return password2 or ""

    def save(self, commit: bool = True) -> User:
        user: User = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class AdminUserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(
        label="Пароль",
        help_text="Пароль хранится в виде хеша. Сменить его можно отдельной формой.",
    )

    class Meta:
        model = User
        fields = (
            "email",
            "password",
            "first_name",
            "last_name",
            "phone",
            "role",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
        )
