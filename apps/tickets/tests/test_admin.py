from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.http import HttpResponse
from django.urls import reverse

from apps.tickets.constants import TicketPriority, TicketStatus
from apps.tickets.models import Ticket, TicketComment
from apps.tickets.services import change_ticket_status

from .base import TicketTestCase


class TicketAdminTests(TicketTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.list_url = reverse("admin:tickets_ticket_changelist")

    def perform_action(
        self,
        action: str,
        ticket: Ticket,
        **data: object,
    ) -> HttpResponse:
        return self.client.post(
            self.list_url,
            data={
                "action": action,
                ACTION_CHECKBOX_NAME: str(ticket.pk),
                "select_across": "0",
                "index": "0",
                **data,
            },
        )

    def test_commandant_sees_all_three_actions(self) -> None:
        self.make_ticket()
        self.client.force_login(self.commandant)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        for action in ("take_in_work", "complete_ticket", "reject_ticket"):
            self.assertContains(response, f'value="{action}"')

    def test_security_cannot_view_or_execute_actions(self) -> None:
        ticket = self.make_ticket()
        self.client.force_login(self.security)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        change_url = reverse("admin:tickets_ticket_change", args=[ticket.pk])
        self.assertEqual(self.client.get(change_url).status_code, 403)
        response = self.perform_action("take_in_work", ticket)
        self.assertEqual(response.status_code, 403)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.NEW)

    def test_creation_and_deletion_are_forbidden(self) -> None:
        ticket = self.make_ticket()
        self.client.force_login(self.commandant)
        self.assertEqual(
            self.client.get(reverse("admin:tickets_ticket_add")).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "admin:tickets_ticket_delete",
                    args=[ticket.pk],
                )
            ).status_code,
            403,
        )

    def test_take_in_work_action_changes_status(self) -> None:
        ticket = self.make_ticket()
        self.client.force_login(self.commandant)
        response = self.perform_action("take_in_work", ticket)
        self.assertEqual(response.status_code, 302)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.IN_PROGRESS)
        self.assertIsNone(ticket.closed_at)

    def test_closing_actions_show_intermediate_page_and_preserve_id(self) -> None:
        self.client.force_login(self.commandant)
        for action in ("complete_ticket", "reject_ticket"):
            with self.subTest(action=action):
                ticket = self.make_ticket(status=TicketStatus.IN_PROGRESS)
                response = self.perform_action(action, ticket)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(
                    response,
                    "admin/tickets/ticket/status_comment.html",
                )
                self.assertContains(response, f'value="{action}"')
                self.assertContains(response, f'value="{ticket.pk}"')
                self.assertContains(response, 'name="comment"')
                ticket.refresh_from_db()
                self.assertEqual(ticket.status, TicketStatus.IN_PROGRESS)
                self.assertFalse(ticket.comments.exists())

    def test_closing_actions_require_comment(self) -> None:
        self.client.force_login(self.commandant)
        for action in ("complete_ticket", "reject_ticket"):
            with self.subTest(action=action):
                ticket = self.make_ticket(status=TicketStatus.IN_PROGRESS)
                response = self.perform_action(
                    action,
                    ticket,
                    confirm_status="1",
                    comment=" \n\t ",
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn("comment", response.context["form"].errors)
                ticket.refresh_from_db()
                self.assertEqual(ticket.status, TicketStatus.IN_PROGRESS)
                self.assertFalse(ticket.comments.exists())

    def test_closing_actions_save_status_date_and_comment(self) -> None:
        self.client.force_login(self.commandant)
        actions = (
            ("complete_ticket", TicketStatus.DONE),
            ("reject_ticket", TicketStatus.REJECTED),
        )
        for action, target in actions:
            with self.subTest(action=action):
                ticket = self.make_ticket(status=TicketStatus.IN_PROGRESS)
                response = self.perform_action(
                    action,
                    ticket,
                    confirm_status="1",
                    comment="  Решение  ",
                )
                self.assertEqual(response.status_code, 302)
                ticket.refresh_from_db()
                self.assertEqual(ticket.status, target)
                self.assertIsNotNone(ticket.closed_at)
                comment = ticket.comments.get()
                self.assertEqual(comment.author_id, self.commandant.pk)
                self.assertEqual(comment.text, "Решение")

    def test_confirmation_rechecks_current_status(self) -> None:
        ticket = self.make_ticket(status=TicketStatus.IN_PROGRESS)
        self.client.force_login(self.commandant)
        self.perform_action("complete_ticket", ticket)
        change_ticket_status(
            ticket_id=ticket.pk,
            actor=self.commandant,
            new_status=TicketStatus.REJECTED,
            comment="Другой комендант отклонил",
        )
        self.perform_action(
            "complete_ticket",
            ticket,
            confirm_status="1",
            comment="Готово",
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.REJECTED)
        self.assertEqual(ticket.comments.count(), 1)

    def test_closing_more_than_one_ticket_is_rejected(self) -> None:
        first = self.make_ticket(status=TicketStatus.IN_PROGRESS)
        second = self.make_ticket(status=TicketStatus.IN_PROGRESS)
        self.client.force_login(self.commandant)
        response = self.client.post(
            self.list_url,
            data={
                "action": "complete_ticket",
                ACTION_CHECKBOX_NAME: [str(first.pk), str(second.pk)],
                "select_across": "0",
                "confirm_status": "1",
                "comment": "Готово",
            },
        )
        self.assertEqual(response.status_code, 302)
        for ticket in (first, second):
            ticket.refresh_from_db()
            self.assertEqual(ticket.status, TicketStatus.IN_PROGRESS)
            self.assertFalse(ticket.comments.exists())

    def test_readonly_fields_and_existing_comment_authors_are_preserved(self) -> None:
        ticket = self.make_ticket()
        existing = TicketComment.objects.create(
            ticket=ticket,
            author=self.student,
            text="Исходный комментарий",
        )
        self.client.force_login(self.commandant)
        response = self.client.post(
            reverse("admin:tickets_ticket_change", args=[ticket.pk]),
            data={
                **self.ticket_data(priority=TicketPriority.HIGH),
                "assigned_to": self.commandant.pk,
                "new_comment": "  Служебный комментарий  ",
                "author": self.other_student.pk,
                "residency": self.ended_residency.pk,
                "status": TicketStatus.DONE,
                "closed_at": "2026-01-01T12:00:00Z",
                "comments-TOTAL_FORMS": "1",
                "comments-INITIAL_FORMS": "1",
                "comments-MIN_NUM_FORMS": "0",
                "comments-MAX_NUM_FORMS": "0",
                "comments-0-id": str(existing.pk),
                "comments-0-ticket": str(ticket.pk),
                "comments-0-author": str(self.commandant.pk),
                "comments-0-text": "Попытка изменить историю",
                "_save": "Сохранить",
            },
        )
        self.assertEqual(response.status_code, 302)
        ticket.refresh_from_db()
        existing.refresh_from_db()
        self.assertEqual(ticket.author_id, self.student.pk)
        self.assertEqual(ticket.residency_id, self.active_residency.pk)
        self.assertEqual(ticket.status, TicketStatus.NEW)
        self.assertIsNone(ticket.closed_at)
        self.assertEqual(existing.author_id, self.student.pk)
        self.assertEqual(existing.text, "Исходный комментарий")
        new_comment = ticket.comments.exclude(pk=existing.pk).get()
        self.assertEqual(new_comment.author_id, self.commandant.pk)
        self.assertEqual(new_comment.text, "Служебный комментарий")
