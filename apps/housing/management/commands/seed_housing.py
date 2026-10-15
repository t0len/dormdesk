
from django.core.management.base import BaseCommand

from apps.housing.constants import BedState, RoomGender, RoomType
from apps.housing.models import Bed, Building, Floor, Room


class Command(BaseCommand):
    help = "Создает тестовые данные для приложения housing"

    def handle(self, *args: object, **options: object) -> None:
        self.stdout.write("Создание тестовых данных...")

        building, created = Building.objects.get_or_create(
            name="Главный корпус",
            defaults={
                "address": "ул. Примерная, 1",
                "description": "Главный корпус общежития",
                "is_active": True,
            },
        )

        if created:
            self.stdout.write(f"Создан корпус: {building.name}")

        for floor_number in range(1, 3):
            floor, _ = Floor.objects.get_or_create(
                building=building,
                number=floor_number,
            )

            for room_number in range(1, 3):
                room, _ = Room.objects.get_or_create(
                    floor=floor,
                    number=f"{floor_number}0{room_number}",
                    defaults={
                        "room_type": RoomType.DOUBLE,
                        "gender": RoomGender.MALE,
                    },
                )

                for bed_number in range(1, 3):
                    Bed.objects.get_or_create(
                        room=room,
                        number=bed_number,
                        defaults={"state": BedState.NORMAL},
                    )

        self.stdout.write(
            self.style.SUCCESS("Тестовые данные успешно созданы.")
        )
