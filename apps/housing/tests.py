from io import StringIO

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.housing.constants import BedState, RoomGender, RoomType
from apps.housing.models import Bed, Building, Floor, Room


class HousingModelTest(TestCase):
    def setUp(self):
        self.building = Building.objects.create(
            name = "Тестовый корпус",
            address = "Тестовый аддресс",
        )
        self.floor = Floor.objects.create(
            building = self.building,
            number = 1,
        )
        self.room = Room.objects.create(
            floor = self.floor,
            number = "101",
            room_type = RoomType.DOUBLE,
            gender = RoomGender.MALE,
        )

    def test_building_str(self) -> None:
            self.assertEqual(str(self.building), "Тестовый корпус")

    def test_floor_number_must_unique_in_building(self) -> None:
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    Room.objects.create(
                        floor = self.floor,
                        number = "101",
                        room_type = RoomType.DOUBLE,
                        gender = RoomGender.MALE,
                    )

    def test_bed_number_must_be_unique_in_room(self) -> None:
            Bed.objects.create(
                room = self.room,
                number = 1,
                state = BedState.NORMAL,
            )

            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    Bed.objects.create(
                        room = self.room,
                        number = 1,
                        state = BedState.NORMAL,
                    )

    def test_seed_command_creates_data(self) -> None:
            output = StringIO()

            call_command("seed_housing", stdout = output)

            self.assertEqual(Building.objects.count(), 2)
            self.assertEqual(Floor.objects.count(), 3)
            self.assertEqual(Room.objects.count(), 5)
            self.assertEqual(Bed.objects.count(), 8)

    def test_seed_command_is_idempotent(self) -> None:
            call_command("seed_housing")
            call_command("seed_housing")

            self.assertEqual(Building.objects.count(), 2)
            self.assertEqual(Floor.objects.count(), 3)
            self.assertEqual(Room.objects.count(), 5)
            self.assertEqual(Bed.objects.count(), 8)
        