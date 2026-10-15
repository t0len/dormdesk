from django.contrib import admin

from apps.housing.constants import BedState
from apps.housing.models import Bed, Building, Floor, Room


class FloorInline(admin.TabularInline):
    model = Floor
    extra = 1


class RoomInline(admin.TabularInline):
    model = Room
    extra = 1


class BedInline(admin.TabularInline):
    model = Bed
    extra = 1


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "is_active", "commandant")
    list_filter = ("is_active",)
    search_fields = ("name", "address")
    inlines = [FloorInline]
    filter_horizontal = ("security",)


@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ("building", "number")
    list_filter = ("building",)
    inlines = [RoomInline]


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("number", "floor", "room_type", "gender")
    list_filter = ("floor__building", "room_type", "gender")
    search_fields = ("number", "floor__building__name")
    inlines = [BedInline]


@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):
    list_display = ("room", "number", "state")
    list_filter = ("state", "room__room_type", "room__floor__building")
    search_fields = ("room__number", "room__floor__building__name")
    actions = ["make_out_of_service", "make_normal"]

    @admin.action(description="Снять выбранные места с эксплуатации")
    def make_out_of_service(self, request, queryset):
        updated = queryset.update(state=BedState.OUT_OF_SERVICE)
        self.message_user(request, f"Снято с эксплуатации мест: {updated}")

    @admin.action(description="Вернуть выбранные места в строй")
    def make_normal(self, request, queryset):
        updated = queryset.update(state=BedState.NORMAL)
        self.message_user(request, f"Возвращено в строй мест: {updated}")
