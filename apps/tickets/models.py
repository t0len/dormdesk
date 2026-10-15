from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import MaxLengthValidator
from django.db import models

from apps.abstracts.models import TimeStampedModel
from apps.residency.constants import ResidencyStatus
from apps.users.constants import Role

from .constants import (
    ALLOWED_STATUS_TRANSITIONS,
    CLOSED_STATUSES,
    COMMENT_PREVIEW_LENGTH,
    MAXIMUM_COMMENT_LENGTH,
    MAXIMUM_LENGTH_FOR_CONSTANTS,
    MAXIMUM_TITLE_LENGTH,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)


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
        super().clean()
        errors: dict[str, list[str]] = {}

        author = None
        residency = None

        if self.author_id:
            try:
                author = self.author
            except ObjectDoesNotExist:
                errors.setdefault("author", []).append("Выбранный автор не существует.")

        if self.residency_id:
            try:
                residency = self.residency
            except ObjectDoesNotExist:
                errors.setdefault("residency", []).append(
                    "Выбранное заселение не существует."
                )

        if author is not None and author.role != Role.STUDENT:
            errors.setdefault("author", []).append(
                "Автором заявки должен быть студент."
            )

        if author is not None and residency is not None:
            if residency.student_id != self.author_id:
                errors.setdefault("residency", []).append(
                    "Заселение должно принадлежать автору заявки."
                )

        if self._state.adding:
            if residency is not None and residency.status != ResidencyStatus.ACTIVE:
                errors.setdefault("residency", []).append(
                    "Создать заявку можно лишь для активного заселения"
                )
            if self.status != TicketStatus.NEW:
                errors.setdefault("status", []).append(
                    'Заявка должна создаваться со статусом "Новая".'
                )
        elif self.pk is not None:
            previous_status = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("status", flat=True)
                .first()
            )

            if previous_status is not None and previous_status != self.status:
                allowed_statuses = ALLOWED_STATUS_TRANSITIONS.get(
                    previous_status, frozenset()
                )

                if self.status not in allowed_statuses:
                    errors.setdefault("status", []).append(
                        "Данный переход статуса запрещён."
                    )

        if self.status in CLOSED_STATUSES:
            if self.closed_at is None:
                errors.setdefault("closed_at", []).append(
                    "У закрытой заявки должна быть дата закрытия."
                )

        elif self.closed_at is not None:
            errors.setdefault("closed_at", []).append(
                "У открытой заявки дата закрытия должна отсутствовать."
            )

        if errors:
            raise ValidationError(errors)


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
        validators=[MaxLengthValidator(MAXIMUM_COMMENT_LENGTH)],
    )

    class Meta:
        verbose_name = "Комментарий"
        verbose_name_plural = "Комментарии"
        ordering = ["created_at", "pk"]

    def __str__(self) -> str:
        return (
            f"Комментарий к заявке #{self.ticket_id}: "
            f"{self.text[:COMMENT_PREVIEW_LENGTH]}"
        )

    def clean(self) -> None:
        super().clean()
        errors = {}

        self.text = (self.text or "").strip()

        if not self.text:
            errors["text"] = "Комментарий не может быть пустым"

        author = None
        ticket = None

        if self.author_id:
            try:
                author = self.author
            except ObjectDoesNotExist:
                errors["author"] = "Данный автор не существует"

        if self.ticket_id:
            try:
                ticket = self.ticket
            except ObjectDoesNotExist:
                errors["ticket"] = "Данной заявки не существует"

        if author is not None:
            if author.role == Role.STUDENT:
                if ticket is not None:
                    if ticket.author_id != self.author_id:
                        errors["ticket"] = (
                            "Студент не может комментировать чужую заявку"
                        )

                    elif ticket.status in CLOSED_STATUSES:
                        errors["ticket"] = (
                            "Студент не может комментировать закрытую заявку"
                        )

            elif author.role != Role.COMMANDANT:
                errors["author"] = (
                    "Комментарии разрешены только студентам и коменданту."
                )

        if errors:
            raise ValidationError(errors)
