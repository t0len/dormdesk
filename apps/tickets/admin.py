from __future__ import annotations

from collections.abc import Callable

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse

from apps.users.services import is_commandant

from .constants import ALLOWED_STATUS_TRANSITIONS, TicketStatus
from .forms import TicketStatusCommentForm
from .models import Ticket, TicketComment
from .services import add_ticket_comment, change_ticket_status


class TicketAdminForm(forms.ModelForm):
    new_comment = forms.CharField(
        label="Новый служебный комментарий",
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
        strip=True,
        max_length=TicketComment._meta.get_field("text").max_length,
        help_text="Автором будет текущий комендант.",
    )

    class Meta:
        model = Ticket
        fields = [
            "category",
            "title",
            "description",
            "photo",
            "priority",
            "assigned_to",
        ]


class TicketCommentInline(admin.TabularInline):
    model = TicketComment
    fields = ("text", "author", "created_at")
    readonly_fields = ("text", "author", "created_at")
    ordering = ("created_at", "pk")
    extra = 0
    can_delete = False

    def has_view_permission(
        self, request: HttpRequest, obj: Ticket | None = None
    ) -> bool:
        return is_commandant(request.user)

    def has_add_permission(
        self, request: HttpRequest, obj: Ticket | None = None
    ) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: Ticket | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: Ticket | None = None
    ) -> bool:
        return False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    form = TicketAdminForm
    inlines = (TicketCommentInline,)

    list_display = (
        "id",
        "title",
        "author",
        "category",
        "priority",
        "status",
        "assigned_to",
        "created_at",
        "closed_at",
    )

    search_fields = (
        "title",
        "author__email",
        "author__first_name",
        "author__last_name",
    )

    list_filter = (
        "status",
        "category",
        "residency__bed__room__floor__building",
    )

    list_select_related = ("author", "assigned_to", "residency")
    ordering = ("-created_at", "-pk")

    readonly_fields = (
        "author",
        "residency",
        "status",
        "closed_at",
        "created_at",
        "updated_at",
    )

    fields = (
        "author",
        "residency",
        "category",
        "title",
        "description",
        "photo",
        "priority",
        "assigned_to",
        "status",
        "closed_at",
        "created_at",
        "updated_at",
        "new_comment",
    )

    actions = ("take_in_work", "complete_ticket", "reject_ticket")

    def has_module_permission(self, request: HttpRequest) -> bool:
        return is_commandant(request.user)

    def has_view_permission(
        self, request: HttpRequest, obj: Ticket | None = None
    ) -> bool:
        return is_commandant(request.user)

    def has_change_permission(
        self, request: HttpRequest, obj: Ticket | None = None
    ) -> bool:
        return is_commandant(request.user)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: Ticket | None = None
    ) -> bool:
        return False

    def get_actions(
        self,
        request: HttpRequest,
    ) -> dict[str, tuple[Callable[..., HttpResponse | None], str, str]]:
        if not is_commandant(request.user):
            return {}

        actions = super().get_actions(request)
        return {
            name: action for name, action in actions.items() if name in self.actions
        }

    def _require_commandant(self, request: HttpRequest) -> None:
        if not is_commandant(request.user):
            raise PermissionDenied("Доступ только для коменданта.")

        if request.method != "POST":
            raise PermissionDenied("Для действия требуется POST.")

    def _list_url(self) -> str:
        opts = self.model._meta
        return reverse(
            f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}_changelist"
        )

    def save_model(
        self,
        request: HttpRequest,
        obj: Ticket,
        form: TicketAdminForm,
        change: bool,
    ) -> None:
        self._require_commandant(request)

        if not change:
            raise PermissionDenied("Создание заявок через админку запрещено.")

        obj.save(
            update_fields=[
                "category",
                "title",
                "description",
                "photo",
                "priority",
                "assigned_to",
                "updated_at",
            ]
        )

        comment = form.cleaned_data.get("new_comment", "")

        if comment:
            add_ticket_comment(
                ticket_id=obj.pk,
                actor=request.user,
                text=comment,
            )

    @admin.action(
        description="Взять в работу",
        permissions=["change"],
    )
    def take_in_work(self, request: HttpRequest, queryset: QuerySet[Ticket]) -> None:
        self._require_commandant(request)
        successful = 0

        for ticket_id in list(queryset.values_list("pk", flat=True)):
            try:
                ticket = change_ticket_status(
                    ticket_id=ticket_id,
                    actor=request.user,
                    new_status=TicketStatus.IN_PROGRESS,
                )
            except ValidationError as error:
                self.message_user(
                    request,
                    f"Заявка №{ticket_id}: {'; '.join(error.messages)}",
                    level=messages.ERROR,
                )
            except Ticket.DoesNotExist:
                self.message_user(
                    request,
                    f"Заявка №{ticket_id} больше не существует.",
                    level=messages.ERROR,
                )
            else:
                self.log_change(request, ticket, "Взята в работу.")
                successful += 1

        if successful:
            self.message_user(
                request,
                f"Взято в работу заявок: {successful}.",
                level=messages.SUCCESS,
            )

    @admin.action(
        description="Завершить",
        permissions=["change"],
    )
    def complete_ticket(
        self,
        request: HttpRequest,
        queryset: QuerySet[Ticket],
    ) -> HttpResponse:
        return self._status_with_comment(
            request,
            queryset,
            new_status=TicketStatus.DONE,
            action_name="complete_ticket",
            title="Завершить заявку",
        )

    @admin.action(
        description="Отклонить",
        permissions=["change"],
    )
    def reject_ticket(
        self,
        request: HttpRequest,
        queryset: QuerySet[Ticket],
    ) -> HttpResponse:
        return self._status_with_comment(
            request,
            queryset,
            new_status=TicketStatus.REJECTED,
            action_name="reject_ticket",
            title="Отклонить заявку",
        )

    def _status_with_comment(
        self,
        request: HttpRequest,
        queryset: QuerySet[Ticket],
        *,
        new_status: TicketStatus,
        action_name: str,
        title: str,
    ) -> HttpResponse:
        self._require_commandant(request)

        selected = list(queryset[:2])

        if len(selected) != 1:
            self.message_user(
                request,
                "Для этого действия выбери ровно одну заявку.",
                level=messages.ERROR,
            )
            return redirect(self._list_url())

        ticket = selected[0]

        allowed = ALLOWED_STATUS_TRANSITIONS.get(
            ticket.status,
            frozenset(),
        )

        if new_status not in allowed:
            self.message_user(
                request,
                "Текущий статус заявки не допускает это действие.",
                level=messages.ERROR,
            )
            return redirect(self._list_url())

        confirmed = request.POST.get("confirm_status") == "1"
        form = TicketStatusCommentForm(
            request.POST if confirmed else None,
        )

        if confirmed and form.is_valid():
            try:
                updated_ticket = change_ticket_status(
                    ticket_id=ticket.pk,
                    actor=request.user,
                    new_status=new_status,
                    comment=form.cleaned_data["comment"],
                )
            except ValidationError as error:
                form.add_error(
                    None,
                    ValidationError(error.messages),
                )
                self.message_user(
                    request,
                    "Статус не изменён. Проверь ошибки формы.",
                    level=messages.ERROR,
                )
            except Ticket.DoesNotExist:
                self.message_user(
                    request,
                    "Заявка больше не существует.",
                    level=messages.ERROR,
                )
                return redirect(self._list_url())
            else:
                self.log_change(
                    request,
                    updated_ticket,
                    f"Статус: {updated_ticket.get_status_display()}.",
                )
                self.message_user(
                    request,
                    "Статус изменён, комментарий сохранён.",
                    level=messages.SUCCESS,
                )
                return redirect(self._list_url())

        context = {
            **self.admin_site.each_context(request),
            "title": title,
            "opts": self.model._meta,
            "ticket": ticket,
            "form": form,
            "action_name": action_name,
            "action_checkbox_name": ACTION_CHECKBOX_NAME,
            "changelist_url": self._list_url(),
            "media": self.media + form.media,
        }

        return TemplateResponse(
            request,
            "admin/tickets/ticket/status_comment.html",
            context,
        )
