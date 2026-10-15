from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.residency.services import active_residency_for
from apps.users.models import User
from apps.users.services import is_student

from .constants import CLOSED_STATUSES
from .forms import TicketCommentForm, TicketForm
from .models import Ticket
from .services import (
    add_ticket_comment,
    create_ticket,
    get_tickets_for_student,
)


def _require_student(user: User | AnonymousUser) -> None:
    if not is_student(user):
        raise PermissionDenied("Этот раздел доступен только студентам.")


def _add_service_errors(
    form: forms.BaseForm,
    error: ValidationError | PermissionDenied,
) -> None:
    """Ошибки отсутствующих в форме полей становятся общими."""
    if isinstance(error, PermissionDenied):
        form.add_error(None, str(error))
        return

    if hasattr(error, "error_dict"):
        for field, field_errors in error.error_dict.items():
            target = field if field in form.fields else None
            form.add_error(target, ValidationError(field_errors))
    else:
        form.add_error(None, error)


def _render_ticket_detail(
    request: HttpRequest,
    ticket: Ticket,
    comment_form: TicketCommentForm | None = None,
    *,
    status: int = 200,
) -> HttpResponse:
    if comment_form is None:
        comment_form = TicketCommentForm()

    return render(
        request,
        "tickets/detail.html",
        {
            "ticket": ticket,
            "comments": (
                ticket.comments.select_related("author").order_by("created_at", "pk")
            ),
            "comment_form": comment_form,
            "can_comment": ticket.status not in CLOSED_STATUSES,
        },
        status=status,
    )


@login_required
@require_GET
def ticket_list(request: HttpRequest) -> HttpResponse:
    _require_student(request.user)

    tickets = get_tickets_for_student(
        student_id=request.user.pk,
    ).order_by("-created_at", "-pk")

    active_residency = active_residency_for(request.user)

    return render(
        request,
        "tickets/list.html",
        {
            "tickets": tickets,
            "active_residency": active_residency,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def ticket_create(request: HttpRequest) -> HttpResponse:
    _require_student(request.user)

    active_residency = active_residency_for(request.user)

    if active_residency is None:
        return render(
            request,
            "tickets/create.html",
            {
                "form": None,
                "no_residency_message": (
                    "Подать заявку на ремонт можно после заселения"
                ),
            },
            status=403 if request.method == "POST" else 200,
        )

    if request.method == "POST":
        form = TicketForm(request.POST, request.FILES)

        if form.is_valid():
            try:
                ticket = create_ticket(
                    actor=request.user,
                    category=form.cleaned_data["category"],
                    title=form.cleaned_data["title"],
                    description=form.cleaned_data["description"],
                    photo=form.cleaned_data.get("photo"),
                    priority=form.cleaned_data["priority"],
                )
            except (ValidationError, PermissionDenied) as error:
                _add_service_errors(form, error)
            else:
                return redirect("tickets:detail", pk=ticket.pk)
    else:
        form = TicketForm()

    return render(
        request,
        "tickets/create.html",
        {"form": form},
    )


@login_required
@require_GET
def ticket_detail(request: HttpRequest, pk: int) -> HttpResponse:
    _require_student(request.user)

    ticket = get_object_or_404(
        Ticket.objects.filter(author=request.user),
        pk=pk,
    )

    return _render_ticket_detail(request, ticket)


@login_required
@require_POST
def ticket_comment_create(request: HttpRequest, pk: int) -> HttpResponse:
    _require_student(request.user)

    ticket = get_object_or_404(
        Ticket.objects.filter(author=request.user),
        pk=pk,
    )

    form = TicketCommentForm(request.POST)

    if ticket.status in CLOSED_STATUSES:
        form.is_valid()
        form.add_error(
            None,
            "Нельзя комментировать закрытую заявку.",
        )
        return _render_ticket_detail(
            request,
            ticket,
            form,
            status=400,
        )

    if form.is_valid():
        try:
            add_ticket_comment(
                ticket_id=ticket.pk,
                actor=request.user,
                text=form.cleaned_data["text"],
            )
        except (ValidationError, PermissionDenied) as error:
            _add_service_errors(form, error)
        else:
            return redirect("tickets:detail", pk=ticket.pk)

    # Статус мог измениться, пока сервис обрабатывал комментарий.
    ticket = get_object_or_404(
        Ticket.objects.filter(author=request.user),
        pk=pk,
    )

    return _render_ticket_detail(
        request,
        ticket,
        form,
        status=400,
    )
