from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.users.forms import (
    EmailAuthenticationForm,
    ProfileUpdateForm,
    StaffProfileForm,
    StudentRegistrationForm,
)
from apps.users.models import StudentProfile, User
from apps.users.services import is_commandant, is_security, is_student


def _student_profile(user: User) -> StudentProfile | None:
    try:
        return user.student_profile
    except StudentProfile.DoesNotExist:
        return None


def home(request: HttpRequest) -> HttpResponse:
    user = request.user
    return render(
        request,
        "users/home.html",
        {
            "show_student_links": is_student(user),
            "show_admin_link": is_commandant(user) or is_security(user),
        },
    )


def register(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("users:home")
    form = StudentRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Регистрация прошла успешно.")
        return redirect("users:home")
    return render(request, "users/register.html", {"form": form})


def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("users:home")
    form = EmailAuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect("users:home")
    return render(request, "users/login.html", {"form": form})


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    user = request.user
    if is_student(user) and _student_profile(user) is None:
        messages.error(
            request,
            "Профиль студента ещё не создан. Его добавляет комендант в админке.",
        )
        return render(
            request,
            "users/profile.html",
            {"form": None, "is_student_profile": True},
        )
    if is_student(user):
        form = ProfileUpdateForm(user, request.POST or None)
    else:
        form = StaffProfileForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Профиль обновлён.")
        return redirect("users:profile")
    return render(
        request,
        "users/profile.html",
        {"form": form, "is_student_profile": is_student(user)},
    )


@login_required
def password_change(request: HttpRequest) -> HttpResponse:
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Пароль изменён.")
        return redirect("users:password_change_done")
    return render(request, "users/password_change.html", {"form": form})


@login_required
def password_change_done(request: HttpRequest) -> HttpResponse:
    return render(request, "users/password_change_done.html")
