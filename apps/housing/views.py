from datetime import date
from typing import Any

from django.db.models import QuerySet
from django.views.generic import DetailView, ListView

from apps.housing.models import Building, Room

try:
    from apps.residency.services import bed_is_occupied
except ImportError:
    from apps.housing.models import Bed

    def bed_is_occupied (bed: Bed, on_date:date) -> bool:
        return False

class BuildingListView(ListView):
    model = Building
    template_name = "housing/building_list.html"
    context_object_name = "buildings"

    def get_queryset(self) -> QuerySet[Building]:
        return Building.objects.filter(is_active=True)

class BuildingDetailView(DetailView):
    model = Building
    template_name = "housing/building_detail.html"

    context_object_name = "building"

    def get_context_data(self, **kwargs:Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        building = self.get_object()
        context["floors"] = building.floors.prefetch_related("rooms__beds").all()
        return context

class RoomDetailView(DetailView):
    model = Room
    template_name = "housing/room_detail.html"
    context_object_name = "room"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        room = self.object()
        today = date.today()

        beds_with_status = []
        for bed in room.beds.all():
            occupied = bed_is_occupied(bed, today)
            beds_with_status.append(
                {
                    "bed":bed,
                    "is_occupied": occupied
                }
            )

        context["beds_with_status"] = beds_with_status
        return context
