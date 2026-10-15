"""Shared fixtures using the team's actual housing and residency fields."""

from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory

from PIL import Image

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from apps.housing.constants import BedState, RoomGender, RoomType
from apps.housing.models import Bed, Building, Floor, Room
from apps.residency.constants import ResidencyStatus
from apps.residency.models import Residency
from apps.tickets.constants import TicketCategory, TicketPriority, TicketStatus
from apps.tickets.models import Ticket
from apps.users.constants import Role
from apps.users.models import User


class TicketTestCase(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.student = cls.make_user("student", Role.STUDENT)
        cls.other_student = cls.make_user("other", Role.STUDENT)
        cls.commandant = cls.make_user("commandant", Role.COMMANDANT)
        cls.security = cls.make_user("security", Role.SECURITY)

        cls.building = Building.objects.create(
            name="Тестовый корпус",
            address="Тестовая улица, 1",
            commandant=cls.commandant,
        )
        cls.floor = Floor.objects.create(building=cls.building, number=1)
        cls.room = Room.objects.create(
            floor=cls.floor,
            number="101",
            room_type=RoomType.DOUBLE,
            gender=RoomGender.MALE,
        )
        cls.bed = Bed.objects.create(
            room=cls.room,
            number=1,
            state=BedState.NORMAL,
        )
        cls.other_bed = Bed.objects.create(
            room=cls.room,
            number=2,
            state=BedState.NORMAL,
        )

        today = timezone.localdate()
        # Fixtures describe stored states, not validation rules of another app.
        # bulk_create preserves real fields and database constraints while keeping
        # Residency.clean() outside the scope of the tickets tests.
        cls.active_residency = Residency(
            student=cls.student,
            bed=cls.bed,
            start_date=today - timedelta(days=10),
            planned_end_date=today + timedelta(days=100),
            status=ResidencyStatus.ACTIVE,
        )
        cls.ended_residency = Residency(
            student=cls.other_student,
            bed=cls.other_bed,
            start_date=today - timedelta(days=100),
            planned_end_date=today - timedelta(days=10),
            actual_end_date=today - timedelta(days=10),
            status=ResidencyStatus.ENDED,
        )
        Residency.objects.bulk_create([cls.active_residency, cls.ended_residency])

    @classmethod
    def make_user(cls, name: str, role: Role) -> User:
        return User.objects.create_user(
            email=f"{name}@dormdesk.test",
            password=None,
            first_name=name,
            last_name="Тестовый",
            phone="+77010000000",
            role=role,
        )

    def setUp(self) -> None:
        super().setUp()
        media = TemporaryDirectory(prefix="dormdesk-tickets-tests-")
        self.addCleanup(media.cleanup)
        self.media_root = media.name
        self.enterContext(self.settings(MEDIA_ROOT=media.name))

    def ticket_data(self, **overrides: object) -> dict[str, object]:
        data = {
            "category": TicketCategory.PLUMBING,
            "title": "Протекает кран",
            "description": "Кран в комнате не закрывается полностью.",
            "priority": TicketPriority.MEDIUM,
        }
        data.update(overrides)
        return data

    def make_ticket(self, **overrides: object) -> Ticket:
        """Persist a known state directly to test reads and transitions from it.

        Ticket.save() deliberately does not call full_clean(). Creation validation
        is tested separately through the service and explicit full_clean().
        """
        data = {
            **self.ticket_data(),
            "author": self.student,
            "residency": self.active_residency,
            "status": TicketStatus.NEW,
        }
        data.update(overrides)
        if data["status"] in {TicketStatus.DONE, TicketStatus.REJECTED}:
            data.setdefault("closed_at", timezone.now())
        return Ticket.objects.create(**data)

    def end_residency(self) -> Residency:
        # Simulate a completed move-out performed by the residency app.
        Residency.objects.filter(pk=self.active_residency.pk).update(
            status=ResidencyStatus.ENDED,
            actual_end_date=timezone.localdate(),
        )
        residency = Residency.objects.get(pk=self.active_residency.pk)
        return residency

    @staticmethod
    def image_upload() -> SimpleUploadedFile:
        content = BytesIO()
        Image.new("RGB", (2, 2), color="blue").save(content, format="PNG")
        return SimpleUploadedFile(
            "repair.png",
            content.getvalue(),
            content_type="image/png",
        )
