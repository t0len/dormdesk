from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from django.db.models import Q

from apps.residency.constants import ResidencyStatus
from apps.residency.models import Residency

if TYPE_CHECKING:
    from apps.housing.models import Bed
    from apps.users.models import User


def bed_is_occupied(bed: Bed, on_date: date) -> bool:
    """Проверяет, занято ли конкретное место в определенный день."""
    return Residency.objects.filter(
        bed=bed,
        status=ResidencyStatus.ACTIVE,
        start_date__lte=on_date,
    ).filter(
        Q(planned_end_date__gte=on_date) | Q(actual_end_date__gte=on_date)
    ).exists()


def active_residency_for(user: User) -> Residency | None:
    """Возвращает текущее активное заселение студента или None."""
    return Residency.objects.filter(
        student=user,
        status=ResidencyStatus.ACTIVE
    ).select_related("bed", "bed__room", "bed__room__floor", "bed__room__floor__building").first()
