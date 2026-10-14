from __future__ import annotations

from typing import Any
from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest

from apps.residency.constants import ApplicationStatus, ResidencyStatus
from apps.residency.models import ApplicationStatusLog, HousingApplication, Residency

class ApplicationStatusLogInline(admin.TabularInline):
    model = ApplicationStatusLog
    extra = 0
    readonly_fields = ("old_status", "new_status", "changed_by", "created_at")
    can_delete = False



@admin.register(HousingApplication)
class HousingApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "preferred_building", "preferred_room_type", "status", "created_at")
    list_filter = ("status", "preferred_room_type", "preferred_building")
    search_fields = ("student__email", "student__first_name", "student__last_name", "comment")
    readonly_fields = ("created_at", "updated_at", "reviewed_at", "reviewed_by")
    inlines = [ApplicationStatusLogInline]
    actions = ["make_approved", "make_rejected"]

    @admin.action(description="Одобрить выбранные заявки")
    def make_approved(self, request: HttpRequest, queryset: QuerySet[HousingApplication]) -> None:
        updated = 0
        for app_obj in queryset.filter(status=ApplicationStatus.PENDING):
            old_status = app_obj.status
            app_obj.status = ApplicationStatus.APPROVED
            app_obj.reviewed_by = request.user
            app_obj.save()
            ApplicationStatusLog.objects.create(
                application=app_obj,
                old_status=old_status,
                new_status=ApplicationStatus.APPROVED,
                changed_by=request.user
            )
            updated += 1
        self.message_user(request, f"Одобрено заявок: {updated}", messages.SUCCESS)

    @admin.action(description="Отклонить выбранные заявки")
    def make_rejected(self, request: HttpRequest, queryset: QuerySet[HousingApplication]) -> None:
        updated = 0
        for app_obj in queryset.filter(status=ApplicationStatus.PENDING):
            old_status = app_obj.status
            app_obj.status = ApplicationStatus.REJECTED
            app_obj.reviewed_by = request.user
            if not app_obj.rejection_reason:
                app_obj.rejection_reason = "Отклонено комендантом через панель управления."
            app_obj.save()
            ApplicationStatusLog.objects.create(
                application=app_obj,
                old_status=old_status,
                new_status=ApplicationStatus.REJECTED,
                changed_by=request.user
            )
            updated += 1
        self.message_user(request, f"Отклонено заявок: {updated}", messages.WARNING)





@admin.register(Residency)
class ResidencyAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "bed", "status", "start_date", "planned_end_date", "actual_end_date")
    list_filter = ("status", "bed__room__floor__building")
    search_fields = ("student__email", "student__first_name", "student__last_name", "bed__room__number")
    readonly_fields = ("created_at", "updated_at")
    actions = ["evict_residents"]

    @admin.action(description="Выселить выбранных студентов (завершить заселение)")
    def evict_residents(self, request: HttpRequest, queryset: QuerySet[Residency]) -> None:
        from django.utils import timezone
        updated = queryset.filter(status=ResidencyStatus.ACTIVE).update(
            status=ResidencyStatus.ENDED,
            actual_end_date=timezone.now().date()
        )
        self.message_user(request, f"Успешно выселено студентов: {updated}", messages.SUCCESS)





@admin.register(ApplicationStatusLog)
class ApplicationStatusLogAdmin(admin.ModelAdmin):
    list_display = ("application", "old_status", "new_status", "changed_by", "created_at")
    list_filter = ("old_status", "new_status")
    readonly_fields = ("application", "old_status", "new_status", "changed_by", "created_at", "updated_at")




