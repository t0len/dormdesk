from django.db import models

MAXIMUM_LENGTH_FOR_CONSTANTS = 20
MAXIMUM_TITLE_LENGTH = 100
MAXIMUM_COMMENT_LENGTH = 200
COMMENT_PREVIEW_LENGTH = 50


class TicketCategory(models.TextChoices):
    PLUMBING = "plumbing", "Сантехника"
    ELECTRICITY = "electricity", "Электрика"
    FURNITURE = "furniture", "Мебель"
    INTERNET = "internet", "Интернет"
    OTHER = "other", "Другое"


class TicketPriority(models.TextChoices):
    LOW = "low", "Низкий"
    MEDIUM = "medium", "Средний"
    HIGH = "high", "Высокий"


class TicketStatus(models.TextChoices):
    NEW = "new", "Новая"
    IN_PROGRESS = "in_progress", "В работе"
    DONE = "done", "Завершена"
    REJECTED = "rejected", "Отклонена"


CLOSED_STATUSES = frozenset(
    {
        TicketStatus.DONE,
        TicketStatus.REJECTED,
    }
)

ALLOWED_STATUS_TRANSITIONS = {
    TicketStatus.NEW: frozenset(
        {
            TicketStatus.IN_PROGRESS,
            TicketStatus.REJECTED,
        }
    ),
    TicketStatus.IN_PROGRESS: frozenset(
        {
            TicketStatus.DONE,
            TicketStatus.REJECTED,
        }
    ),
    TicketStatus.DONE: frozenset(),
    TicketStatus.REJECTED: frozenset(),
}
