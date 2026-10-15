from django.conf import settings
from django.urls import reverse

from apps.tickets.constants import TicketStatus
from apps.tickets.models import Ticket

from .base import TicketTestCase


class TicketViewTests(TicketTestCase):
    def test_guest_is_redirected_to_login_on_all_endpoints(self) -> None:
        ticket = self.make_ticket()
        endpoints = (
            ("get", reverse("tickets:list")),
            ("get", reverse("tickets:create")),
            ("post", reverse("tickets:create")),
            ("get", reverse("tickets:detail", args=[ticket.pk])),
            ("post", reverse("tickets:comment_create", args=[ticket.pk])),
        )
        login_url = reverse(settings.LOGIN_URL)
        for method, url in endpoints:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url)
                self.assertRedirects(
                    response,
                    f"{login_url}?next={url}",
                    fetch_redirect_response=False,
                )

    def test_staff_receive_403_on_student_pages(self) -> None:
        ticket = self.make_ticket()
        endpoints = (
            ("get", reverse("tickets:list")),
            ("get", reverse("tickets:create")),
            ("post", reverse("tickets:create")),
            ("get", reverse("tickets:detail", args=[ticket.pk])),
            ("post", reverse("tickets:comment_create", args=[ticket.pk])),
        )
        for actor in (self.commandant, self.security):
            self.client.force_login(actor)
            for method, url in endpoints:
                with self.subTest(actor=actor.role, method=method, url=url):
                    self.assertEqual(
                        getattr(self.client, method)(url).status_code,
                        403,
                    )

    def test_list_contains_only_own_tickets(self) -> None:
        own = self.make_ticket(title="Своя заявка")
        other = self.make_ticket(
            author=self.other_student,
            residency=self.ended_residency,
            title="Чужая заявка",
        )
        self.client.force_login(self.student)
        response = self.client.get(reverse("tickets:list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["tickets"]), [own])
        self.assertContains(response, own.title)
        self.assertNotContains(response, other.title)

    def test_empty_list_has_helpful_message(self) -> None:
        self.client.force_login(self.student)
        response = self.client.get(reverse("tickets:list"))
        self.assertContains(response, "пока нет заявок")

    def test_student_can_create_without_photo(self) -> None:
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("tickets:create"),
            data=self.ticket_data(),
        )
        ticket = Ticket.objects.get()
        self.assertRedirects(
            response,
            reverse("tickets:detail", args=[ticket.pk]),
        )
        self.assertEqual(ticket.author_id, self.student.pk)
        self.assertEqual(ticket.residency_id, self.active_residency.pk)
        self.assertEqual(ticket.status, TicketStatus.NEW)
        self.assertFalse(ticket.photo)

    def test_student_can_create_with_image(self) -> None:
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("tickets:create"),
            data={**self.ticket_data(), "photo": self.image_upload()},
        )
        ticket = Ticket.objects.get()
        self.assertRedirects(
            response,
            reverse("tickets:detail", args=[ticket.pk]),
        )
        self.assertTrue(ticket.photo.storage.exists(ticket.photo.name))
        detail = self.client.get(reverse("tickets:detail", args=[ticket.pk]))
        self.assertContains(detail, ticket.photo.url)

    def test_create_form_accepts_file_uploads(self) -> None:
        self.client.force_login(self.student)
        response = self.client.get(reverse("tickets:create"))
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_without_active_residency_get_hides_form_and_post_is_denied(self) -> None:
        self.client.force_login(self.other_student)
        url = reverse("tickets:create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Подать заявку на ремонт можно после заселения",
        )
        self.assertIsNone(response.context["form"])

        response = self.client.post(url, data=self.ticket_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Ticket.objects.exists())

    def test_post_cannot_override_server_owned_fields(self) -> None:
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("tickets:create"),
            data={
                **self.ticket_data(),
                "author": self.other_student.pk,
                "residency": self.ended_residency.pk,
                "status": TicketStatus.DONE,
                "assigned_to": self.security.pk,
                "closed_at": "2026-01-01T12:00:00Z",
            },
        )
        ticket = Ticket.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ticket.author_id, self.student.pk)
        self.assertEqual(ticket.residency_id, self.active_residency.pk)
        self.assertEqual(ticket.status, TicketStatus.NEW)
        self.assertIsNone(ticket.assigned_to_id)
        self.assertIsNone(ticket.closed_at)

    def test_other_students_detail_and_comment_endpoint_return_404(self) -> None:
        ticket = self.make_ticket()
        self.client.force_login(self.other_student)
        response = self.client.get(reverse("tickets:detail", args=[ticket.pk]))
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            reverse("tickets:comment_create", args=[ticket.pk]),
            data={"text": "Чужой комментарий"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(ticket.comments.exists())

    def test_comment_endpoint_requires_post(self) -> None:
        ticket = self.make_ticket()
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("tickets:comment_create", args=[ticket.pk]),
        )
        self.assertEqual(response.status_code, 405)
        self.assertFalse(ticket.comments.exists())

    def test_comment_author_is_current_user(self) -> None:
        ticket = self.make_ticket()
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("tickets:comment_create", args=[ticket.pk]),
            data={"text": "  Ещё течёт  ", "author": self.commandant.pk},
        )
        self.assertRedirects(
            response,
            reverse("tickets:detail", args=[ticket.pk]),
        )
        comment = ticket.comments.get()
        self.assertEqual(comment.author_id, self.student.pk)
        self.assertEqual(comment.text, "Ещё течёт")

    def test_blank_comment_shows_form_error(self) -> None:
        ticket = self.make_ticket()
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("tickets:comment_create", args=[ticket.pk]),
            data={"text": " \n\t "},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("text", response.context["comment_form"].errors)
        self.assertFalse(ticket.comments.exists())

    def test_closed_ticket_hides_form_and_rejects_direct_post(self) -> None:
        self.client.force_login(self.student)
        for status in (TicketStatus.DONE, TicketStatus.REJECTED):
            with self.subTest(status=status):
                ticket = self.make_ticket(status=status)
                detail_url = reverse("tickets:detail", args=[ticket.pk])
                comment_url = reverse("tickets:comment_create", args=[ticket.pk])
                response = self.client.get(detail_url)
                self.assertFalse(response.context["can_comment"])
                self.assertNotContains(response, f'action="{comment_url}"')
                response = self.client.post(
                    comment_url,
                    data={"text": "Обход скрытой кнопки"},
                )
                self.assertEqual(response.status_code, 400)
                self.assertTrue(
                    response.context["comment_form"].non_field_errors(),
                )
                self.assertFalse(ticket.comments.exists())

    def test_ticket_remains_accessible_after_residency_ends(self) -> None:
        ticket = self.make_ticket()
        self.end_residency()
        self.client.force_login(self.student)
        response = self.client.get(reverse("tickets:list"))
        self.assertContains(response, ticket.title)
        self.assertIsNone(response.context["active_residency"])
        response = self.client.get(reverse("tickets:detail", args=[ticket.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Комментариев пока нет")

    def test_detail_shows_russian_choice_labels(self) -> None:
        ticket = self.make_ticket()
        self.client.force_login(self.student)
        response = self.client.get(reverse("tickets:detail", args=[ticket.pk]))
        for label in (
            ticket.get_category_display(),
            ticket.get_priority_display(),
            ticket.get_status_display(),
        ):
            self.assertContains(response, label)
