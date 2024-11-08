from django import forms
from django.contrib.auth.models import User
from .models import SportProfile, TeamCategory, SportRequirement, Team, Sport
from users.models import Profile

class TeamCategoryForm(forms.ModelForm):
    class Meta:
        model = TeamCategory
        fields = ['name']

class SportRequirementForm(forms.ModelForm):
    allowed_category = forms.ModelChoiceField(
        queryset=TeamCategory.objects.none(),  # Initialize with an empty queryset
        widget=forms.Select,  # Dropdown for single selection
        required=True,
        label="Team Category"
    )

    class Meta:
        model = SportRequirement
        fields = ['number_of_teams', 'players_per_team', 'allowed_category', 'entrance_fee']  
        widgets = {
            'entrance_fee': forms.NumberInput(attrs={
                'class': 'border border-gray-600 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            }),
            'number_of_teams': forms.NumberInput(attrs={
                'class': 'border border-gray-600 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            }),
            'players_per_team': forms.NumberInput(attrs={
                'class': 'border border-gray-600 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'event') and hasattr(self.instance, 'sport'):
            # Filter the queryset based on the event and sport of the instance
            queryset = TeamCategory.objects.filter(
                event=self.instance.event,
                sport=self.instance.sport
            )
            # Assign queryset to the allowed_category field for the dropdown
            self.fields['allowed_category'].queryset = queryset


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
        


class TeamRegistrationForm(forms.Form):
    team_name = forms.ModelChoiceField(
        queryset=Team.objects.none(),  # Default to empty queryset; will be updated in __init__
        label="Team Name",
        widget=forms.Select(attrs={"class": "form-control"})
    )
    entrance_fee = forms.DecimalField(
        min_value=0, 
        max_digits=10, decimal_places=2,
        label="Entrance Fee",
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )
    coach_name = forms.CharField(
        max_length=100, 
        disabled=True,
        label="Coach Name",
        initial='',  # This will be set in the view
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    sport_id = forms.ModelChoiceField(
        queryset=Sport.objects.all(),  # Assuming this is how you store the sport types
        label="Sport",
        widget=forms.Select(attrs={"class": "form-control"})
    )
    players = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(profile__role='Player'),  # Assuming 'Player' is a role in a related profile
        widget=forms.CheckboxSelectMultiple,
        label="Players"
    )

    def __init__(self, *args, **kwargs):
        coach_id = kwargs.pop('coach_id', None)  # Expecting coach_id to be passed in kwargs
        sport_id = kwargs.pop('sport_id', None)  # Expecting sport_id from the modal's selection
        coach_name = kwargs.pop('coach_name', 'No Coach')  # Default fallback if no coach_name is passed
        super().__init__(*args, **kwargs)

        # Initialize the coach_name field with the passed value
        if coach_name:
            self.fields['coach_name'].initial = coach_name

        if coach_id:
            # Filter teams by the logged-in coach's ID
            self.fields['team_name'].queryset = Team.objects.filter(COACH_ID=coach_id)
            
        if sport_id:
            # Filter teams by the sport selected by the coach (optional but can improve UX)
            self.fields['team_name'].queryset = self.fields['team_name'].queryset.filter(SPORT_ID=sport_id)

    def clean_entrance_fee(self):
        fee = self.cleaned_data['entrance_fee']
        if fee < 0:
            raise forms.ValidationError("Entrance fee must be a positive number.")
        return fee


