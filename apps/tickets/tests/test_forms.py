from django.test import SimpleTestCase

from apps.tickets.constants import TicketCategory, TicketPriority
from apps.tickets.forms import (
    TicketCommentForm,
    TicketForm,
    TicketStatusCommentForm,
)
from apps.tickets.models import TicketComment


class TicketFormTests(SimpleTestCase):
    def test_student_form_exposes_only_allowed_fields(self) -> None:
        self.assertEqual(
            list(TicketForm().fields),
            ["category", "title", "description", "photo", "priority"],
        )

    def test_server_fields_are_not_accepted_as_form_fields(self) -> None:
        form = TicketForm(
            data={
                "category": TicketCategory.PLUMBING,
                "title": "Кран",
                "description": "Протекает",
                "priority": TicketPriority.MEDIUM,
                "author": 999,
                "residency": 999,
                "status": "done",
                "assigned_to": 999,
                "closed_at": "2026-01-01T12:00:00Z",
            }
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())
        for field in ("author", "residency", "status", "assigned_to", "closed_at"):
            self.assertNotIn(field, form.cleaned_data)

    def test_invalid_category_is_rejected(self) -> None:
        form = TicketForm(
            data={
                "category": "unknown",
                "title": "Кран",
                "description": "Протекает",
                "priority": TicketPriority.MEDIUM,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)

    def test_comment_form_exposes_only_text(self) -> None:
        self.assertEqual(list(TicketCommentForm().fields), ["text"])

    def test_comment_form_rejects_whitespace_only(self) -> None:
        form = TicketCommentForm(data={"text": " \n\t "})
        self.assertFalse(form.is_valid())
        self.assertIn("text", form.errors)

    def test_status_comment_is_required_and_trimmed(self) -> None:
        for value in ("", "   ", "\n\t"):
            with self.subTest(value=value):
                form = TicketStatusCommentForm(data={"comment": value})
                self.assertFalse(form.is_valid())
                self.assertIn("comment", form.errors)

        form = TicketStatusCommentForm(data={"comment": "  Готово  "})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["comment"], "Готово")

    def test_status_comment_respects_model_text_limit(self) -> None:
        limit = TicketComment._meta.get_field("text").max_length
        form = TicketStatusCommentForm(data={"comment": "x" * (limit + 1)})
        self.assertFalse(form.is_valid())
        self.assertIn("comment", form.errors)
