from django.db import models


class ApplicationStatus(models.TextChoices):
    PENDING = "pending", "На рассмотрении"
    APPROVED = "approved", "Одобрена"
    REJECTED = "rejected", "Отклонена"
    CANCELLED = "cancelled", "Отменена студентом"


class ResidencyStatus(models.TextChoices):
    ACTIVE = "active", "Активно (заселен)"
    ENDED = "ended", "Выселен"


class RoomTypeChoice(models.TextChoices):
    DOUBLE = "double", "Двухместная"
    TRIPLE = "triple", "Трехместная"
    QUAD = "quad", "Четырехместная"
