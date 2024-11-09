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
    # entrance_fee = forms.DecimalField(
    #     min_value=0, 
    #     max_digits=10, decimal_places=2,
    #     label="Entrance Fee",
    #     widget=forms.NumberInput(attrs={"class": "form-control"})
    # )
    coach_name = forms.CharField(
        max_length=100, 
        disabled=True,
        label="Coach Name",
        initial='',  # This will be set in the view
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    sport_id = forms.CharField(
        widget=forms.HiddenInput()  # This will ensure the field is not rendered as a select box
    )
    players = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="Players"
    )

    def __init__(self, *args, **kwargs):
        coach_id = kwargs.pop('coach_id', None)  
        sport_id = kwargs.pop('sport_id', None)  
        coach_name = kwargs.pop('coach_name', 'No Coach')  
        super().__init__(*args, **kwargs)

        if coach_name:
            self.fields['coach_name'].initial = coach_name

        if coach_id:
            self.fields['team_name'].queryset = Team.objects.filter(COACH_ID=coach_id)

        if sport_id:
            self.fields['team_name'].queryset = self.fields['team_name'].queryset.filter(SPORT_ID=sport_id)
            
            # Filter players who are associated with the same sport as the coach (e.g., basketball)
            available_players = User.objects.filter(
                profile__role='Player', 
                profile__sports__id=sport_id
            )

            # Update the players queryset to only include those linked to the selected sport
            self.fields['players'].queryset = available_players

            # Debugging: Print the available players for sport_id
            print(f"Available players for sport_id {sport_id}:")
            for player in available_players:
                print(f"Player: {player.username}, Sports: {player.profile.sports.all()}")

            # Set the hidden field sport_id with the passed value
            self.fields['sport_id'].initial = sport_id

    def clean_players(self):
        players = self.cleaned_data.get('players')
        sport_id = self.cleaned_data.get('sport_id')

        # Debugging: Print the selected players and their associated sports
        print(f"Selected players: {', '.join([p.username for p in players])}")

        # Ensure that each selected player belongs to the selected sport
        for player in players:
            if not player.profile.sports.filter(id=sport_id).exists():
                raise forms.ValidationError(f"Player {player.username} does not belong to the selected sport.")
        
        return players


    # def clean_entrance_fee(self):
    #     fee = self.cleaned_data['entrance_fee']
    #     if fee < 0:
    #         raise forms.ValidationError("Entrance fee must be a positive number.")
    #     return fee


