from django import forms
from django.contrib.auth.models import User
from .models import *
from users.models import Profile




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
                profile__sports__SPORT_ID=sport_id
            ).distinct()
                
            for player in available_players:
                sport_names = player.profile.sports.values_list('SPORT_ID__SPORT_NAME', flat=True)
                # print(f"Player: {player.username}, Sports: {list(sport_names)}")
            self.fields['players'].queryset = available_players
        else:
            print("Sport ID not found during form initialization")



    def clean_players(self):
        players = self.cleaned_data.get('players')
        sport_id = self.cleaned_data.get('sport_id')
        

        for player in players:
            if not player.profile.sports.filter(SPORT_ID=sport_id).exists():
                raise forms.ValidationError(f"Player {player.username} does not belong to the selected sport.")
        return players





    # def clean_entrance_fee(self):
    #     fee = self.cleaned_data['entrance_fee']
    #     if fee < 0:
    #         raise forms.ValidationError("Entrance fee must be a positive number.")
    #     return fee


class BasketballStatsForm(forms.ModelForm):
    class Meta:
        model = BasketballStats
        fields = ['points', 'rebounds', 'assists', 'blocks', 'steals', 'turnovers', 'three_pointers_made', 'free_throws_made']
        widgets = {
            'points': forms.NumberInput(attrs={'class': 'form-control'}),
            'rebounds': forms.NumberInput(attrs={'class': 'form-control'}),
            'assists': forms.NumberInput(attrs={'class': 'form-control'}),
            'blocks': forms.NumberInput(attrs={'class': 'form-control'}),
            'steals': forms.NumberInput(attrs={'class': 'form-control'}),
            'turnovers': forms.NumberInput(attrs={'class': 'form-control'}),
            'three_pointers_made': forms.NumberInput(attrs={'class': 'form-control'}),
            'free_throws_made': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class VolleyballStatsForm(forms.ModelForm):
    class Meta:
        model = VolleyballStats
        fields = ['kills', 'blocks','blocks_score', 'digs', 'service_aces', 'attack_errors', 'reception_errors', 'assists']
        widgets = {
            'kills': forms.NumberInput(attrs={'class': 'form-control'}),
            'blocks': forms.NumberInput(attrs={'class': 'form-control'}),
            'blocks_score': forms.NumberInput(attrs={'class': 'form-control'}),
            'digs': forms.NumberInput(attrs={'class': 'form-control'}),
            'service_aces': forms.NumberInput(attrs={'class': 'form-control'}),
            'attack_errors': forms.NumberInput(attrs={'class': 'form-control'}),
            'reception_errors': forms.NumberInput(attrs={'class': 'form-control'}),
            'assists': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
