from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.residency.models import Residency
from apps.tickets.constants import TicketStatus
from apps.tickets.models import Ticket, TicketComment
from apps.tickets.services import (
    add_ticket_comment,
    change_ticket_status,
    create_ticket,
    get_tickets_for_student,
)

from .base import TicketTestCase


class TicketCreationServiceTests(TicketTestCase):
    def test_student_with_active_residency_creates_new_ticket(self) -> None:
        ticket = create_ticket(actor=self.student, **self.ticket_data())
        ticket.refresh_from_db()
        self.assertEqual(ticket.author_id, self.student.pk)
        self.assertEqual(ticket.residency_id, self.active_residency.pk)
        self.assertEqual(ticket.status, TicketStatus.NEW)
        self.assertIsNone(ticket.closed_at)
        self.assertFalse(ticket.photo)

    def test_student_without_active_residency_cannot_create(self) -> None:
        with self.assertRaises(ValidationError):
            create_ticket(actor=self.other_student, **self.ticket_data())
        self.assertFalse(Ticket.objects.exists())

    def test_staff_and_guest_cannot_create(self) -> None:
        for actor in (self.commandant, self.security, AnonymousUser()):
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionDenied):
                    create_ticket(actor=actor, **self.ticket_data())
        self.assertFalse(Ticket.objects.exists())

    def test_invalid_model_data_is_not_saved(self) -> None:
        for overrides in ({"category": "invalid"}, {"title": ""}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValidationError):
                    create_ticket(
                        actor=self.student,
                        **self.ticket_data(**overrides),
                    )
        self.assertFalse(Ticket.objects.exists())

    def test_valid_photo_is_saved_inside_temporary_media_root(self) -> None:
        ticket = create_ticket(
            actor=self.student,
            **self.ticket_data(),
            photo=self.image_upload(),
        )
        self.assertTrue(ticket.photo.storage.exists(ticket.photo.name))
        self.assertTrue(ticket.photo.name.startswith("tickets/"))
        with ticket.photo.open("rb") as image:
            self.assertEqual(image.read(8), b"\x89PNG\r\n\x1a\n")

    def test_student_query_contains_only_own_tickets(self) -> None:
        own = self.make_ticket()
        self.make_ticket(
            author=self.other_student,
            residency=self.ended_residency,
        )
        self.assertEqual(
            list(get_tickets_for_student(self.student.pk)),
            [own],
        )

    def test_history_remains_visible_after_residency_ends(self) -> None:
        ticket = self.make_ticket()
        self.end_residency()
        self.assertIn(ticket, get_tickets_for_student(self.student.pk))


class TicketCommentServiceTests(TicketTestCase):
    def test_student_comments_on_own_open_ticket(self) -> None:
        for status in (TicketStatus.NEW, TicketStatus.IN_PROGRESS):
            with self.subTest(status=status):
                ticket = self.make_ticket(status=status)
                comment = add_ticket_comment(
                    ticket_id=ticket.pk,
                    actor=self.student,
                    text="  Спасибо!  ",
                )
                comment.refresh_from_db()
                self.assertEqual(comment.author_id, self.student.pk)
                self.assertEqual(comment.ticket_id, ticket.pk)
                self.assertEqual(comment.text, "Спасибо!")

    def test_other_student_and_security_cannot_comment(self) -> None:
        ticket = self.make_ticket()
        for actor in (self.other_student, self.security, AnonymousUser()):
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionDenied):
                    add_ticket_comment(
                        ticket_id=ticket.pk,
                        actor=actor,
                        text="Комментарий",
                    )
        self.assertFalse(ticket.comments.exists())

    def test_student_cannot_comment_on_closed_ticket(self) -> None:
        for status in (TicketStatus.DONE, TicketStatus.REJECTED):
            with self.subTest(status=status):
                ticket = self.make_ticket(status=status)
                with self.assertRaises(ValidationError):
                    add_ticket_comment(
                        ticket_id=ticket.pk,
                        actor=self.student,
                        text="Комментарий",
                    )
                self.assertFalse(ticket.comments.exists())

    def test_commandant_can_comment_on_closed_ticket(self) -> None:
        ticket = self.make_ticket(status=TicketStatus.DONE)
        comment = add_ticket_comment(
            ticket_id=ticket.pk,
            actor=self.commandant,
            text="Служебная запись",
        )
        self.assertEqual(comment.author_id, self.commandant.pk)

    def test_blank_and_too_long_comments_are_not_saved(self) -> None:
        ticket = self.make_ticket()
        limit = TicketComment._meta.get_field("text").max_length
        for text in ("", " \n\t ", "x" * (limit + 1)):
            with self.subTest(text=text):
                with self.assertRaises(ValidationError):
                    add_ticket_comment(
                        ticket_id=ticket.pk,
                        actor=self.student,
                        text=text,
                    )
        self.assertFalse(ticket.comments.exists())


class TicketStatusServiceTests(TicketTestCase):
    def test_all_four_allowed_transitions(self) -> None:
        transitions = (
            (TicketStatus.NEW, TicketStatus.IN_PROGRESS),
            (TicketStatus.NEW, TicketStatus.REJECTED),
            (TicketStatus.IN_PROGRESS, TicketStatus.DONE),
            (TicketStatus.IN_PROGRESS, TicketStatus.REJECTED),
        )
        for source, target in transitions:
            with self.subTest(source=source, target=target):
                ticket = self.make_ticket(status=source)
                before = timezone.now()
                changed = change_ticket_status(
                    ticket_id=ticket.pk,
                    actor=self.commandant,
                    new_status=target,
                    comment="  Работы выполнены / решение принято.  ",
                )
                after = timezone.now()
                ticket.refresh_from_db()
                self.assertEqual(changed.pk, ticket.pk)
                self.assertEqual(ticket.status, target)
                if target == TicketStatus.IN_PROGRESS:
                    self.assertIsNone(ticket.closed_at)
                else:
                    self.assertLessEqual(before, ticket.closed_at)
                    self.assertLessEqual(ticket.closed_at, after)
                comment = ticket.comments.get()
                self.assertEqual(comment.author_id, self.commandant.pk)
                self.assertEqual(
                    comment.text,
                    "Работы выполнены / решение принято.",
                )

    def test_taking_in_work_does_not_require_comment(self) -> None:
        ticket = self.make_ticket()
        change_ticket_status(
            ticket_id=ticket.pk,
            actor=self.commandant,
            new_status=TicketStatus.IN_PROGRESS,
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.IN_PROGRESS)
        self.assertIsNone(ticket.closed_at)
        self.assertFalse(ticket.comments.exists())

    def test_new_to_done_is_forbidden(self) -> None:
        ticket = self.make_ticket()
        with self.assertRaises(ValidationError):
            change_ticket_status(
                ticket_id=ticket.pk,
                actor=self.commandant,
                new_status=TicketStatus.DONE,
                comment="Готово",
            )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.NEW)
        self.assertIsNone(ticket.closed_at)
        self.assertFalse(ticket.comments.exists())

    def test_closed_tickets_cannot_transition_to_any_status(self) -> None:
        for source in (TicketStatus.DONE, TicketStatus.REJECTED):
            ticket = self.make_ticket(status=source)
            old_closed_at = ticket.closed_at
            for target in TicketStatus.values:
                with self.subTest(source=source, target=target):
                    with self.assertRaises(ValidationError):
                        change_ticket_status(
                            ticket_id=ticket.pk,
                            actor=self.commandant,
                            new_status=target,
                            comment="Изменение",
                        )
                    ticket.refresh_from_db()
                    self.assertEqual(ticket.status, source)
                    self.assertEqual(ticket.closed_at, old_closed_at)
                    self.assertFalse(ticket.comments.exists())

    def test_student_security_and_guest_cannot_change_status(self) -> None:
        ticket = self.make_ticket()
        for actor in (self.student, self.security, AnonymousUser()):
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionDenied):
                    change_ticket_status(
                        ticket_id=ticket.pk,
                        actor=actor,
                        new_status=TicketStatus.IN_PROGRESS,
                    )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.NEW)

    def test_closing_requires_nonblank_comment(self) -> None:
        for target in (TicketStatus.DONE, TicketStatus.REJECTED):
            for text in ("", "   ", "\n\t"):
                with self.subTest(target=target, text=text):
                    ticket = self.make_ticket(status=TicketStatus.IN_PROGRESS)
                    with self.assertRaises(ValidationError):
                        change_ticket_status(
                            ticket_id=ticket.pk,
                            actor=self.commandant,
                            new_status=target,
                            comment=text,
                        )
                    ticket.refresh_from_db()
                    self.assertEqual(ticket.status, TicketStatus.IN_PROGRESS)
                    self.assertIsNone(ticket.closed_at)
                    self.assertFalse(ticket.comments.exists())

    def test_comment_save_failure_rolls_back_status_date_and_comment(self) -> None:
        ticket = self.make_ticket(status=TicketStatus.IN_PROGRESS)
        old_updated_at = ticket.updated_at
        original_save = TicketComment.save

        def save_then_fail(
            instance: TicketComment,
            *args: object,
            **kwargs: object,
        ) -> None:
            original_save(instance, *args, **kwargs)
            raise RuntimeError("Simulated failure after inserting a comment")

        with patch.object(TicketComment, "save", new=save_then_fail):
            with self.assertRaisesRegex(RuntimeError, "Simulated failure"):
                change_ticket_status(
                    ticket_id=ticket.pk,
                    actor=self.commandant,
                    new_status=TicketStatus.DONE,
                    comment="Ремонт завершён",
                )

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.IN_PROGRESS)
        self.assertIsNone(ticket.closed_at)
        self.assertEqual(ticket.updated_at, old_updated_at)
        self.assertFalse(ticket.comments.exists())

    def test_too_long_closing_comment_rolls_back_status(self) -> None:
        ticket = self.make_ticket(status=TicketStatus.IN_PROGRESS)
        limit = TicketComment._meta.get_field("text").max_length
        with self.assertRaises(ValidationError):
            change_ticket_status(
                ticket_id=ticket.pk,
                actor=self.commandant,
                new_status=TicketStatus.DONE,
                comment="x" * (limit + 1),
            )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.IN_PROGRESS)
        self.assertIsNone(ticket.closed_at)
        self.assertFalse(ticket.comments.exists())

    def test_commandant_can_finish_ticket_after_student_moves_out(self) -> None:
        ticket = self.make_ticket(status=TicketStatus.IN_PROGRESS)
        self.end_residency()
        change_ticket_status(
            ticket_id=ticket.pk,
            actor=self.commandant,
            new_status=TicketStatus.DONE,
            comment="Закончили после выселения",
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.DONE)
        self.assertIsNotNone(ticket.closed_at)
        self.assertEqual(ticket.comments.count(), 1)
        self.assertEqual(
            Residency.objects.get(pk=ticket.residency_id).student_id,
            self.student.pk,
        )
