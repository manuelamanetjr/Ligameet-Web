from django import forms
from .models import Event, SportProfile
from users.models import Profile

class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'EVENT_NAME', 'EVENT_LOCATION', 'EVENT_DATE_START', 'EVENT_DATE_END', 
            'SPORT', 'EVENT_IMAGE', 'NUMBER_OF_TEAMS', 'PLAYERS_PER_TEAM', 
            'CONTACT_PERSON', 'CONTACT_PHONE'
        ]

        widgets = {
            'EVENT_NAME': forms.TextInput(attrs={
                'class': 'mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
                'placeholder': 'Enter event name'
            }),
            'EVENT_LOCATION': forms.TextInput(attrs={
                'class': 'mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
                'id': 'pac-input',  # ID used by Google Maps autocomplete
                'placeholder': 'Enter event location'
            }),
            'EVENT_DATE_START': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'
            }),
            'EVENT_DATE_END': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'
            }),
            'SPORT': forms.SelectMultiple(attrs={
                'class': 'mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'
            }),
            'EVENT_IMAGE': forms.FileInput(attrs={
                'class': 'mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
                'accept': 'image/*'
            }),
            'NUMBER_OF_TEAMS': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
                'min': '1'
            }),
            'PLAYERS_PER_TEAM': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
                'min': '1'
            }),
            'CONTACT_PERSON': forms.TextInput(attrs={
                'class': 'mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
                'placeholder': 'Enter contact person'
            }),
            'CONTACT_PHONE': forms.TextInput(attrs={
                'type': 'tel',
                'class': 'mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
                'placeholder': 'Enter contact phone number'
            }),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        event_date_start = cleaned_data.get('EVENT_DATE_START')
        event_date_end = cleaned_data.get('EVENT_DATE_END')

        if event_date_start and event_date_end and event_date_start >= event_date_end:
            raise forms.ValidationError("End date must be after start date.")
        
        return cleaned_data



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


class ScoutPlayerFilterForm(forms.Form):
    position = forms.MultipleChoiceField(
        choices=[],  # Choices are populated dynamically
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'border border-gray-300 p-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary custom-checkbox-group'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set the position choices to include all available positions
        self.fields['position'].choices = Profile.get_all_positions()


