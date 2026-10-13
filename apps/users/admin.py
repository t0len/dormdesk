from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import QuerySet
from django.http import HttpRequest

from apps.users.forms import AdminUserChangeForm, AdminUserCreationForm
from apps.users.models import StudentProfile, User


class StudentProfileInline(admin.StackedInline):
    model = StudentProfile
    extra = 0
    max_num = 1


@admin.action(description="Деактивировать выбранных пользователей")
def deactivate_users(
    modeladmin: admin.ModelAdmin,
    request: HttpRequest,
    queryset: QuerySet[User],
) -> None:
    queryset.update(is_active=False)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = AdminUserChangeForm
    add_form = AdminUserCreationForm
    inlines = (StudentProfileInline,)
    list_display = (
        "email",
        "last_name",
        "first_name",
        "role",
        "phone",
        "is_staff",
        "is_active",
    )
    list_filter = ("role",)
    search_fields = ("email", "last_name", "student_profile__student_number")
    ordering = ("email",)
    filter_horizontal = ("groups", "user_permissions")
    readonly_fields = ("created_at", "updated_at", "last_login")
    actions = (deactivate_users,)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Личные данные",
            {"fields": ("first_name", "last_name", "phone", "role")},
        ),
        (
            "Права",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Даты", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "phone",
                    "role",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
