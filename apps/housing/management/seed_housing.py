from django.core.management.base import BaseCommand
from apps.housing.constants import BedState, RoomGender, RoomType
from apps.housing.models import Building, Floor, Room, Bed

class Command(BaseCommand):
    help = "Создает тестовые данные"

    def handle(self, *args, **options):
        self.stdout.write("Создание тестовых данных...")

        building, created = Building.objects.get_or_create(
            name = "Главный корпус",
            defaults = {
                "address": "ул. Примерная, 1",
                "description": "Главный корпус общежития",
                "is_active": True,
            },
        )

        if created:
            self.stdout.write(f"Создан корпус: {building.name}")

        for floor_num in range(1,3):
            floor, _ = Floor.objects.get_or_create(building = building, number = floor_num)

            for room_num_suffix in [10,20]:
                room_number = f"{floor_num}0{room_num_suffix // 10}"
                room, _ = Room.objects.get_or_create(
                    floor = floor,
                    number = room_number,
                    defaults = {
                        "room_type": RoomType.BOUBLE,
                        "gender": RoomGender.MALE,
                    }
                )

                for bed_num in range(1, 3):
                    Bed.objects.get_or_create(
                        room = room,
                        number = bed_num,
                        defaults = {"state": BedState.NORMAL}
                    )
        self.stdout.write(self.style.SUCCESS("Тестовые данные успешно созданы."))