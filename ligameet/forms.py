from django import forms
from .models import Event, SportProfile
from users.models import Profile

class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'EVENT_NAME', 
            'EVENT_LOCATION', 
            'EVENT_DATE_START', 
            'EVENT_DATE_END', 
            'EVENT_STATUS', 
            'SPORT', 
            'NUMBER_OF_TEAMS', 
            'PLAYERS_PER_TEAM', 
            'PAYMENT_FEE', 
            'CONTACT_PERSON', 
            'CONTACT_PHONE', 
            'EVENT_IMAGE', 
            'IS_SPONSORED'
        ]
        widgets = {
            'EVENT_NAME': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'EVENT_LOCATION': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'EVENT_DATE_START': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control', 'required': 'required'}),
            'EVENT_DATE_END': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control', 'required': 'required'}),
            'EVENT_STATUS': forms.Select(attrs={'class': 'form-select', 'required': 'required'}),
            'SPORT': forms.Select(attrs={'class': 'form-select', 'required': 'required'}),
            'NUMBER_OF_TEAMS': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'required': 'required'}),
            'PLAYERS_PER_TEAM': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'required': 'required'}),
            'PAYMENT_FEE': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01', 'required': 'required'}),
            'CONTACT_PERSON': forms.TextInput(attrs={'class': 'form-control'}),
            'CONTACT_PHONE': forms.TextInput(attrs={'class': 'form-control'}),
            'EVENT_IMAGE': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'IS_SPONSORED': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'isSponsored'}),
        }


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
                    
# forms.py
class PlayerFilterForm(forms.Form):
    position = forms.MultipleChoiceField(
        choices=[],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'border border-gray-300 p-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary custom-checkbox-group'
        })
    )

    def __init__(self, *args, **kwargs):
        coach = kwargs.pop('coach', None)  # Get the coach instance
        super().__init__(*args, **kwargs)
        if coach:
            sport_profile = SportProfile.objects.filter(USER_ID=coach).first()
            if sport_profile:
                sport = sport_profile.SPORT_ID.SPORT_NAME.lower()
                if sport == 'basketball':
                    self.fields['position'].choices = Profile.BASKETBALL_POSITIONS
                elif sport == 'volleyball':
                    self.fields['position'].choices = Profile.VOLLEYBALL_POSITIONS



