from django import forms
from .models import Event

class EventDetailForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'EVENT_NAME', 
            'EVENT_DATE_START', 
            'EVENT_DATE_END', 
            'EVENT_IMAGE',
            'NUMBER_OF_TEAMS',
            'PLAYERS_PER_TEAM',
            'IS_SPONSORED',
            'PAYMENT_FEE'
        ]
