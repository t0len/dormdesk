from __future__ import annotations

from typing import Any

from django import forms

from apps.residency.models import HousingApplication


class HousingApplicationForm(forms.ModelForm):
    class Meta:
        model = HousingApplication
        fields = ["preferred_building", "preferred_room_type", "comment"]
        widgets = {
            "preferred_building": forms.Select(attrs={"class": "form-control"}),
            "preferred_room_type": forms.Select(attrs={"class": "form-control"}),
            "comment": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["preferred_building"].queryset = self.fields["preferred_building"].queryset.filter(is_active=True)
