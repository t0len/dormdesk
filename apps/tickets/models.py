from django.conf import settings
from django.db import models
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from apps.abstracts.models import TimeStampedModel
from apps.users.constants import Role
from .constants import (
    ALLOWED_STATUS_TRANSITIONS,
    CLOSED_STATUSES,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)

MAXIMUM_LENGTH_FOR_CONSTANTS = 20
MAXIMUM_TITLE_LENGTH = 100
MAXIMUM_COMMENT_LENGTH = 200

class Ticket(TimeStampedModel):
    residency = models.ForeignKey(
        "residency.Residency",
        on_delete=models.PROTECT,
        related_name="tickets",
        verbose_name="заселение",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tickets",
        verbose_name="автор",
    )

    category = models.CharField(
        "Категория",
        max_length=MAXIMUM_LENGTH_FOR_CONSTANTS,
        choices=TicketCategory.choices,
    )

    title = models.CharField(
        "Заголовок",
        max_length=MAXIMUM_TITLE_LENGTH,
        )

    description = models.TextField("Описание")

    photo = models.ImageField(
        "Фото",
        upload_to="tickets/%Y/%m/",
        blank=True,
    )

    priority = models.CharField(
        "Приоритет",
        max_length=MAXIMUM_LENGTH_FOR_CONSTANTS,
        choices=TicketPriority.choices,
        default=TicketPriority.MEDIUM,
    )

    status = models.CharField(
        "Статус",
        max_length=MAXIMUM_LENGTH_FOR_CONSTANTS,
        choices=TicketStatus.choices,
        default=TicketStatus.NEW,
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_tickets",
        verbose_name="Исполнитель",
        blank=True,
        null=True,
    )

    closed_at = models.DateTimeField(
        "Дата закрытия",
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = "Заявка на ремонт"
        verbose_name_plural = "Заявки на ремонт"
        ordering = ["-created_at", "-pk"]

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        errors = {}

        author = None
        residency = None

        if self.auhor_id:
            try:
                author = self.author
            except ObjectDoesNotExist:
                errors["author"] = "Выбранный автор не существует."

        if self.residency_id:
            try:
                residency = self.residency
            except ObjectDoesNotExist:
                errors["residency"] = "Выбранное заселение не существует."

class TicketComment(TimeStampedModel):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="Заявка",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="comments",
        verbose_name="Автор",
    )

    text = models.TextField(
        "Текст",
        max_length=MAXIMUM_COMMENT_LENGTH,
    )

    class Meta:
        verbose_name = "Комментарий"
        verbose_name_plural = "Комментарии"
        ordering = ["created_at", "pk"]

    def __str__(self) -> str:
        return f"Комментарий к заявке #{self.ticket_id}: {self.text[:50]}"









