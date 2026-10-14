from django.db import models

class RoomType(models.TextChoices):
    DOUBLE = "double", "Двухместная"
    TRIPLE = "triple", "Трехместная"
    QUAD = "quad", "Четырехместная"

class BedState(models.TextChoices):
    NORMAL = "normal", "В норме"
    OUT_OF_SERVICE = "out_of_service", "Снято с эксплуатации"

class RoomGender(models.TextChoices):
    MALE = "male", "Мужской"
    FEMALE = "female", "Женская"