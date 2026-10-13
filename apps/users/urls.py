from django.contrib.auth.views import LogoutView
from django.urls import path

from apps.users.views import (
    home,
    login_view,
    password_change,
    password_change_done,
    profile,
    register,
)

app_name = "users"

urlpatterns = [
    path("", home, name="home"),
    path("register/", register, name="register"),
    path("login/", login_view, name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("password/", password_change, name="password_change"),
    path("password/done/", password_change_done, name="password_change_done"),
    path("profile/", profile, name="profile"),
]
