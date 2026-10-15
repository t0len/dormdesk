from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.residency.services import active_residency_for
from apps.users.models import User
from apps.users.services import is_commandant, is_student

from .constants import (
    ALLOWED_STATUS_TRANSITIONS,
    CLOSED_STATUSES,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from .models import Ticket, TicketComment


def get_tickets_for_student(student_id: int) -> QuerySet[Ticket]:
    return Ticket.objects.filter(author_id=student_id).select_related(
        "residency", "assigned_to"
    )


def create_ticket(
    *,
    actor: User,
    category: TicketCategory,
    title: str,
    description: str,
    photo: UploadedFile | None = None,
    priority: TicketPriority = TicketPriority.MEDIUM,
) -> Ticket:
    if not is_student(actor):
        raise PermissionDenied("Создавать заявки может только студент.")

    residency = active_residency_for(actor)

    if residency is None:
        raise ValidationError("Для создания заявки необходимо активное заселение.")

    ticket = Ticket(
        author=actor,
        residency=residency,
        category=category,
        title=title.strip(),
        description=description.strip(),
        photo=photo,
        priority=priority,
        status=TicketStatus.NEW,
    )

    ticket.full_clean()
    ticket.save()

    return ticket


@transaction.atomic
def add_ticket_comment(
    *,
    ticket_id: int,
    actor: User,
    text: str,
) -> TicketComment:
    student = is_student(actor)

    if not student and not is_commandant(actor):
        raise PermissionDenied("Комментарии разрешены только студентам и коменданту.")

    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    if student:
        if ticket.author_id != actor.pk:
            raise PermissionDenied("Нельзя комментировать чужую заявку.")

        if ticket.status in CLOSED_STATUSES:
            raise ValidationError("Нельзя комментировать закрытую заявку.")

    text = (text or "").strip()

    if not text:
        raise ValidationError({"text": "Введите текст комментария."})

    ticket_comment = TicketComment(
        ticket=ticket,
        author=actor,
        text=text,
    )

    ticket_comment.full_clean()
    ticket_comment.save()

    return ticket_comment


@transaction.atomic
def change_ticket_status(
    *,
    ticket_id: int,
    actor: User,
    new_status: TicketStatus,
    comment: str = "",
) -> Ticket:
    if not is_commandant(actor):
        raise PermissionDenied("Статус заявки может менять только комендант.")

    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    allowed_statuses = ALLOWED_STATUS_TRANSITIONS.get(
        ticket.status,
        frozenset(),
    )

    if new_status not in allowed_statuses:
        raise ValidationError({"status": "Недопустимый переход статуса."})

    comment = (comment or "").strip()

    if new_status in CLOSED_STATUSES and not comment:
        raise ValidationError({"comment": "Для закрытия заявки нужен комментарий."})

    ticket.status = new_status
    ticket.closed_at = timezone.now() if new_status in CLOSED_STATUSES else None

    ticket.full_clean()
    ticket.save(update_fields=["status", "closed_at", "updated_at"])

    if comment:
        add_ticket_comment(
            ticket_id=ticket.pk,
            actor=actor,
            text=comment,
        )

    return ticket
