from django import forms
from .models import SportProfile, TeamCategory, SportRequirement
from users.models import Profile

class TeamCategoryForm(forms.ModelForm):
    class Meta:
        model = TeamCategory
        fields = ['name']

class SportRequirementForm(forms.ModelForm):
    team_categories = forms.ModelMultipleChoiceField(
        queryset=TeamCategory.objects.none(),  # Initialize with an empty queryset
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Team Categories"
    )

    class Meta:
        model = SportRequirement
        fields = ['number_of_teams', 'players_per_team', 'team_categories']  # Ensure this matches the field name
        widgets = {
            'number_of_teams': forms.NumberInput(attrs={
                'class': 'border border-gray-600 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            }),
            'players_per_team': forms.NumberInput(attrs={
                'class': 'border border-gray-600 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter team categories by the event and sport associated with the SportRequirement instance
        if self.instance and self.instance.event and self.instance.sport:
            self.fields['team_categories'].queryset = TeamCategory.objects.filter(
                event=self.instance.event,
                sport=self.instance.sport
            )



    




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


