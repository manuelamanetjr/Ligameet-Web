from django import forms
from .models import SportProfile, TeamCategory, SportRequirement
from users.models import Profile

class TeamCategoryForm(forms.ModelForm):
    new_category = forms.CharField(max_length=100, required=False, label='New Category')

    class Meta:
        model = TeamCategory
        fields = ['name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].widget.attrs.update({'class': 'flex-grow border rounded px-2 py-1 text-sm'})
        self.fields['new_category'].widget.attrs.update({'class': 'flex-grow border rounded px-2 py-1 text-sm', 'placeholder': 'New category'})

class SportRequirementForm(forms.ModelForm):
    allowed_categories = forms.ModelMultipleChoiceField(
        queryset=TeamCategory.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Allowed Categories'
    )

    class Meta:
        model = SportRequirement
        fields = ['number_of_teams', 'players_per_team', 'allowed_categories']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['number_of_teams'].widget.attrs.update({'class': 'border rounded px-2 py-1 text-sm w-16'})
        self.fields['players_per_team'].widget.attrs.update({'class': 'border rounded px-2 py-1 text-sm w-16'})

                  
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


