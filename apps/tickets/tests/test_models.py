from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.tickets.constants import TicketStatus
from apps.tickets.models import Ticket, TicketComment

from .base import TicketTestCase


class TicketModelTests(TicketTestCase):
    def assert_field_error(self, obj: Ticket, field: str) -> None:
        with self.assertRaises(ValidationError) as caught:
            obj.full_clean()
        self.assertIn(field, caught.exception.message_dict)

    def test_author_must_be_student(self) -> None:
        ticket = Ticket(
            **self.ticket_data(),
            author=self.commandant,
            residency=self.active_residency,
        )
        self.assert_field_error(ticket, "author")

    def test_cannot_use_another_students_residency(self) -> None:
        ticket = Ticket(
            **self.ticket_data(),
            author=self.other_student,
            residency=self.active_residency,
        )
        self.assert_field_error(ticket, "residency")

    def test_new_ticket_requires_active_residency(self) -> None:
        ticket = Ticket(
            **self.ticket_data(),
            author=self.other_student,
            residency=self.ended_residency,
        )
        self.assert_field_error(ticket, "residency")

    def test_residency_errors_are_accumulated_for_same_field(self) -> None:
        ticket = Ticket(
            **self.ticket_data(),
            author=self.student,
            residency=self.ended_residency,
        )
        with self.assertRaises(ValidationError) as caught:
            ticket.full_clean()
        self.assertEqual(len(caught.exception.message_dict["residency"]), 2)

    def test_nonexistent_foreign_keys_report_validation_errors(self) -> None:
        ticket = Ticket(
            **self.ticket_data(),
            author_id=max(self.student.pk, self.security.pk) + 100,
            residency_id=self.ended_residency.pk + 100,
        )
        with self.assertRaises(ValidationError) as caught:
            ticket.full_clean()
        self.assertIn("author", caught.exception.message_dict)
        self.assertIn("residency", caught.exception.message_dict)

    def test_new_ticket_must_start_as_new(self) -> None:
        for status in (
            TicketStatus.IN_PROGRESS,
            TicketStatus.DONE,
            TicketStatus.REJECTED,
        ):
            with self.subTest(status=status):
                ticket = Ticket(
                    **self.ticket_data(),
                    author=self.student,
                    residency=self.active_residency,
                    status=status,
                )
                if status in {TicketStatus.DONE, TicketStatus.REJECTED}:
                    ticket.closed_at = timezone.now()
                self.assert_field_error(ticket, "status")

    def test_closed_ticket_requires_closed_at(self) -> None:
        for status in (TicketStatus.DONE, TicketStatus.REJECTED):
            with self.subTest(status=status):
                ticket = self.make_ticket(status=status)
                ticket.closed_at = None
                self.assert_field_error(ticket, "closed_at")

    def test_open_ticket_cannot_have_closed_at(self) -> None:
        for status in (TicketStatus.NEW, TicketStatus.IN_PROGRESS):
            with self.subTest(status=status):
                ticket = self.make_ticket(status=status)
                ticket.closed_at = timezone.now()
                self.assert_field_error(ticket, "closed_at")

    def test_transition_is_checked_against_database_status(self) -> None:
        ticket = self.make_ticket(status=TicketStatus.IN_PROGRESS)
        # Another writer has already closed this ticket. The Python instance is stale.
        Ticket.objects.filter(pk=ticket.pk).update(
            status=TicketStatus.DONE,
            closed_at=timezone.now(),
        )
        ticket.status = TicketStatus.REJECTED
        ticket.closed_at = timezone.now()
        self.assert_field_error(ticket, "status")

    def test_clean_handles_unfilled_relations(self) -> None:
        ticket = Ticket(**self.ticket_data())
        ticket.clean()

    def test_full_clean_reports_missing_relations(self) -> None:
        ticket = Ticket(**self.ticket_data())
        with self.assertRaises(ValidationError) as caught:
            ticket.full_clean()
        self.assertIn("author", caught.exception.message_dict)
        self.assertIn("residency", caught.exception.message_dict)

    def test_tickets_order_newest_first_with_pk_tiebreaker(self) -> None:
        first = self.make_ticket()
        second = self.make_ticket()
        Ticket.objects.filter(pk__in=[first.pk, second.pk]).update(
            created_at=timezone.now(),
        )
        self.assertEqual(list(Ticket.objects.all()), [second, first])


class TicketCommentModelTests(TicketTestCase):
    def test_comment_trims_surrounding_whitespace(self) -> None:
        comment = TicketComment(
            ticket=self.make_ticket(),
            author=self.student,
            text=" \n Кран всё ещё течёт. \t ",
        )
        comment.full_clean()
        self.assertEqual(comment.text, "Кран всё ещё течёт.")

    def test_blank_comment_is_invalid(self) -> None:
        for text in ("", "   ", "\n\t"):
            with self.subTest(text=text):
                comment = TicketComment(
                    ticket=self.make_ticket(),
                    author=self.student,
                    text=text,
                )
                with self.assertRaises(ValidationError) as caught:
                    comment.full_clean()
                self.assertIn("text", caught.exception.message_dict)

    def test_student_cannot_comment_on_another_students_ticket(self) -> None:
        comment = TicketComment(
            ticket=self.make_ticket(),
            author=self.other_student,
            text="Чужая заявка",
        )
        with self.assertRaises(ValidationError) as caught:
            comment.full_clean()
        self.assertIn("ticket", caught.exception.message_dict)

    def test_student_cannot_comment_on_closed_tickets(self) -> None:
        for status in (TicketStatus.DONE, TicketStatus.REJECTED):
            with self.subTest(status=status):
                comment = TicketComment(
                    ticket=self.make_ticket(status=status),
                    author=self.student,
                    text="Комментарий",
                )
                with self.assertRaises(ValidationError):
                    comment.full_clean()

    def test_commandant_can_comment_on_closed_tickets(self) -> None:
        for status in (TicketStatus.DONE, TicketStatus.REJECTED):
            with self.subTest(status=status):
                comment = TicketComment(
                    ticket=self.make_ticket(status=status),
                    author=self.commandant,
                    text="Служебный комментарий",
                )
                comment.full_clean()

    def test_security_cannot_comment(self) -> None:
        comment = TicketComment(
            ticket=self.make_ticket(),
            author=self.security,
            text="Комментарий",
        )
        with self.assertRaises(ValidationError) as caught:
            comment.full_clean()
        self.assertIn("author", caught.exception.message_dict)

    def test_clean_handles_unfilled_relations(self) -> None:
        TicketComment(text="Комментарий").clean()

    def test_comments_order_oldest_first_with_pk_tiebreaker(self) -> None:
        ticket = self.make_ticket()
        first = TicketComment.objects.create(
            ticket=ticket,
            author=self.student,
            text="Первый",
        )
        second = TicketComment.objects.create(
            ticket=ticket,
            author=self.commandant,
            text="Второй",
        )
        TicketComment.objects.filter(pk__in=[first.pk, second.pk]).update(
            created_at=timezone.now(),
        )
        self.assertEqual(list(ticket.comments.all()), [first, second])
