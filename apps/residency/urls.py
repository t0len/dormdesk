from __future__ import annotations

from django.urls import path

from apps.residency.views import (
    HousingApplicationCancelView,
    HousingApplicationCreateView,
    HousingApplicationListView,
    ResidencyDetailView,
)

app_name = "residency"

urlpatterns = [
    path("applications/", HousingApplicationListView.as_view(), name="application_list"),
    path("applications/create/", HousingApplicationCreateView.as_view(), name="application_create"),
    path("applications/<int:pk>/cancel/", HousingApplicationCancelView.as_view(), name="application_cancel"),
    path("my-room/", ResidencyDetailView.as_view(), name="my_residency"),
]
