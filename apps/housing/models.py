from django.conf import settings
from django.db import models

from apps.abstracts.models import TimeStampedModel
from apps.housing.constants import BedState, RoomGender, RoomType


class Building(TimeStampedModel):
    name = models.CharField("Название", max_length = 100)
    address = models.CharField("Адресс", max_length = 200)
    description = models.TextField("Описание", blank = True )
    is_active = models.BooleanField("Активен", default = True)
    commandant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete = models.SET_NULL,
        null = True,
        blank = True,
        related_name = "managed_buildings",
        verbose_name = "Комендант"
    )
    security = models.ManyToManyField (
        settings.AUTH_USER_MODEL,
        blank = True,
        related_name = "secured_buildings",
        verbose_name = "Охрана",
    )

    class Meta:
        verbose_name = "Корпус"
        verbose_name_plural = "Корпуса"

    def __str__(self) -> str:
        return self.name

class Floor(TimeStampedModel):
    building = models.ForeignKey(
        Building,
        on_delete = models.CASCADE,
        related_name = "floors",
        verbose_name = "Корпус",
    )
    number = models.PositiveSmallIntegerField("Номер этажа")

    class Meta:
        verbose_name = "Этаж"
        verbose_name_plural = "Этажи"
        constraints = [
            models.UniqueConstraint(
                fields = ["building", "number"],
                name = "unique_building_floor"
            )
        ]

    def __str__(self) ->str:
        return f"{self.building.name} - Этаж {self.number}"

class Room(TimeStampedModel):
    floor = models.ForeignKey(
        Floor,
        on_delete = models.CASCADE,
        related_name = "rooms",
        verbose_name = "Этаж",

    )
    number = models.CharField("Номер комнаты", max_length = 20)
    room_type = models.CharField(
        "Тип комнаты",
        max_length = 20,
        choices = RoomType.choices,
        default = RoomType.DOUBLE
    )
    gender = models.CharField(
        "Для кого",
        max_length = 10,
        choices = RoomGender.choices,
    )

    class Meta:
        verbose_name = "Комната",
        verbose_name_plural = "Комнаты",
        constraints = [
            models.UniqueConstraint(
                fields = ["floor", "number"], name = "unique_floor_room"
            )
        ]

    def __str__(self) -> str:
        return f"{self.floor.building.name} - Этаж {self.floor.number} - Комната {self.number}"

class Bed(TimeStampedModel):
    room = models.ForeignKey(
        "Room",
        on_delete = models.CASCADE,
        related_name = "beds",
        verbose_name = "Комната",
    )
    number = models.PositiveSmallIntegerField("Номер места")
    state = models.CharField(
        "Состояние",
        max_length = 20,
        choices = BedState.choices,
        default = BedState.NORMAL,
    )

    class Meta:
        verbose_name = "Место",
        verbose_name_plural = "Места",
        constraints = [
            models.UniqueConstraint(
                fields = ["room", "number"], name = "unique_room_bed"
            )
        ]

    def __str__(self) -> str:
        return f"Место №{self.number} ({self.room})"