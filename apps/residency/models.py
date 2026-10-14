from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from django.core.exceptions import ValidationError
from django.db import models

from apps.abstracts.models import TimeStampedModel
from apps.residency.constants import ApplicationStatus, ResidencyStatus, RoomTypeChoice

if TYPE_CHECKING:
    from apps.housing.models import Bed, Building
    from apps.users.models import User


class HousingApplication(TimeStampedModel):
    student: models.ForeignKey[User] = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="housing_applications",
        verbose_name="Студент",
    )
    preferred_building: models.ForeignKey[Building] = models.ForeignKey(
        "housing.Building",
        on_delete=models.PROTECT,
        related_name="applications",
        verbose_name="Желаемый корпус",
    )
    preferred_room_type: models.CharField = models.CharField(
        max_length=20,
        choices=RoomTypeChoice.choices,
        verbose_name="Желаемый тип комнаты",
    )
    comment: models.TextField = models.TextField(
        blank=True, verbose_name="Комментарий"
    )
    status: models.CharField = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.PENDING,
        verbose_name="Статус",
    )
    reviewed_by: models.ForeignKey[User | None] = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_applications",
        verbose_name="Кто рассмотрел",
    )
    reviewed_at: models.DateTimeField = models.DateTimeField(
        null=True, blank=True, verbose_name="Дата рассмотрения"
    )
    rejection_reason: models.TextField = models.TextField(
        blank=True, verbose_name="Причина отказа"
    )

    class Meta:
        verbose_name = "Заявка на заселение"
        verbose_name_plural = "Заявки на заселение"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Заявка #{self.id} — {self.student.email} ({self.get_status_display()})"

    def clean(self) -> None:
        super().clean()
        
        # 1. У студента только одна заявка в статусе pending 
        if self.status == ApplicationStatus.PENDING:
            existing_pending = HousingApplication.objects.filter(
                student=self.student,
                status=ApplicationStatus.PENDING
            ).exclude(pk=self.pk)
            if existing_pending.exists():
                raise ValidationError("У вас уже есть активная заявка на рассмотрении.")

        # 2. Отказ без причины - не сохраняется
        if self.status == ApplicationStatus.REJECTED and not self.rejection_reason.strip():
            raise ValidationError({"rejection_reason": "Укажите причину отказа по заявке."})

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class Residency(TimeStampedModel):
    student: models.ForeignKey[User] = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="residencies",
        verbose_name="Студент",
    )
    bed: models.ForeignKey[Bed] = models.ForeignKey(
        "housing.Bed",
        on_delete=models.PROTECT,
        related_name="residencies",
        verbose_name="Место",
    )
    application: models.OneToOneField[HousingApplication | None] = models.OneToOneField(
        HousingApplication,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="residency",
        verbose_name="Заявка",
    )
    start_date: models.DateField = models.DateField(verbose_name="Дата начала")
    planned_end_date: models.DateField = models.DateField(verbose_name="Плановая дата выезда")
    actual_end_date: models.DateField = models.DateField(
        null=True, blank=True, verbose_name="Фактическая дата выезда"
    )
    status: models.CharField = models.CharField(
        max_length=20,
        choices=ResidencyStatus.choices,
        default=ResidencyStatus.ACTIVE,
        verbose_name="Статус заселения",
    )

    class Meta:
        verbose_name = "Заселение"
        verbose_name_plural = "Заселения"
        ordering = ["-start_date"]

    def __str__(self) -> str:
        return f"Заселение: {self.student.email} -> Место {self.bed}"

    def clean(self) -> None:
        super().clean()

        # 1. шығу после кіру
        if self.start_date and self.planned_end_date and self.planned_end_date <= self.start_date:
            raise ValidationError({"planned_end_date": "Плановая дата выезда должна быть позже даты начала."})

        # 2. бір рет ғана кіру
        if self.status == ResidencyStatus.ACTIVE:
            active_res = Residency.objects.filter(
                student=self.student,
                status=ResidencyStatus.ACTIVE
            ).exclude(pk=self.pk)
            if active_res.exists():
                raise ValidationError("У этого студента уже есть активное заселение.")

        # 3. Комната пригодна или нет (проверяем, если bed загружен)
        if hasattr(self, "bed") and self.bed and self.bed.status != "normal":
            raise ValidationError({"bed": "Нельзя заселить на место, снятое с эксплуатации."})

        # 4. На одно место нет двух активных заселений с пересекающимися датами
        if self.status == ResidencyStatus.ACTIVE and hasattr(self, "bed") and self.bed:
            end_check = self.planned_end_date
            overlapping = Residency.objects.filter(
                bed=self.bed,
                status=ResidencyStatus.ACTIVE
            ).exclude(pk=self.pk)

            for existing in overlapping:
                exist_start = existing.start_date
                exist_end = existing.actual_end_date or existing.planned_end_date
                # Проверка пересечения отрезков дат
                if not (end_check < exist_start or self.start_date > exist_end):
                    raise ValidationError("На это место уже есть активное пересекающееся по датам заселение.")

        # 5. При выселении статус ended требует фактическую дату
        if self.status == ResidencyStatus.ENDED and not self.actual_end_date:
            raise ValidationError({"actual_end_date": "При выселении необходимо указать фактическую дату выезда."})

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class ApplicationStatusLog(TimeStampedModel):
    application: models.ForeignKey[HousingApplication] = models.ForeignKey(
        HousingApplication,
        on_delete=models.CASCADE,
        related_name="status_logs",
        verbose_name="Заявка",
    )
    old_status: models.CharField = models.CharField(
        max_length=20, choices=ApplicationStatus.choices, verbose_name="Старый статус"
    )
    new_status: models.CharField = models.CharField(
        max_length=20, choices=ApplicationStatus.choices, verbose_name="Новый статус"
    )
    changed_by: models.ForeignKey[User] = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        verbose_name="Кто изменил",
    )

    class Meta:
        verbose_name = "Лог статуса заявки"
        verbose_name_plural = "Логи статусов заявок"

    def __str__(self) -> str:
        return f"Заявка #{self.application_id}: {self.old_status} -> {self.new_status}"
