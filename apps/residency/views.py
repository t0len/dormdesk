from __future__ import annotations
from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from apps.residency.constants import ApplicationStatus
from apps.residency.forms import HousingApplicationForm
from apps.residency.models import HousingApplication, Residency
from apps.residency.services import active_residency_for

class HousingApplicationListView(LoginRequiredMixin, ListView):
    model = HousingApplication
    template_name = "residency/application_list.html"
    context_object_name = "applications"

    def get_queryset(self) -> Any:
        return HousingApplication.objects.filter(student=self.request.user).select_related("preferred_building")

class HousingApplicationCreateView(LoginRequiredMixin, CreateView):
    model = HousingApplication
    form_class = HousingApplicationForm
    template_name = "residency/application_form.html"
    success_url = reverse_lazy("residency:application_list")

    def form_valid(self, form: Any) -> HttpResponse:
        form.instance.student = self.request.user
        return super().form_valid(form)

class HousingApplicationCancelView(LoginRequiredMixin, UpdateView):
    model = HousingApplication
    fields = []
    template_name = "residency/application_confirm_cancel.html"
    success_url = reverse_lazy("residency:application_list")

    def get_object(self, queryset: Any = None) -> HousingApplication:
        obj = super().get_object(queryset)
        if obj.student != self.request.user:
            raise PermissionDenied("Чужую заявку отменить нельзя.")
        if obj.status != ApplicationStatus.PENDING:
            raise PermissionDenied("Можно отменить только заявку в статусе 'На рассмотрении'.")
        return obj

    def form_valid(self, form: Any) -> HttpResponse:
        app_obj = self.object
        old_status = app_obj.status
        app_obj.status = ApplicationStatus.CANCELLED
        app_obj.save()
        
        from apps.residency.models import ApplicationStatusLog
        ApplicationStatusLog.objects.create(
            application=app_obj,
            old_status=old_status,
            new_status=ApplicationStatus.CANCELLED,
            changed_by=self.request.user
        )
        return redirect(self.success_url)


class ResidencyDetailView(LoginRequiredMixin, DetailView):
    model = Residency
    template_name = "residency/residency_detail.html"
    context_object_name = "residency"

    def get_object(self, queryset: Any = None) -> Residency | None:
        return active_residency_for(self.request.user)
