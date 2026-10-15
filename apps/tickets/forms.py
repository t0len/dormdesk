from django import forms

from .models import Ticket, TicketComment


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = [
            "category",
            "title",
            "description",
            "photo",
            "priority",
        ]


class TicketCommentForm(forms.ModelForm):
    class Meta:
        model = TicketComment
        fields = ["text"]


class TicketStatusCommentForm(forms.Form):
    comment = forms.CharField(
        label="Комментарий",
        widget=forms.Textarea(attrs={"rows": 4}),
        strip=True,
        required=True,
        max_length=TicketComment._meta.get_field("text").max_length,
    )
