from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Profile
from django.forms.widgets import DateInput


class UserRegisterForm(UserCreationForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['username', 'email',]


class ProfileUpdateForm(forms.ModelForm):
    PHONE = forms.RegexField(
        regex=r'^(09|\+639)\d{9}$',  # Adjust the regex according to your mobile number format
        error_messages={
            'invalid': 'Enter a valid mobile number. Example: 09XXXXXXXXX or +639XXXXXXXXX'
        }
    )

    class Meta:
        model = Profile
        fields = ['image', 'FIRST_NAME', 'LAST_NAME', 'MIDDLE_NAME', 'DATE_OF_BIRTH', 'GENDER', 'ADDRESS', 'HEIGHT', 'WEIGHT', 'PHONE']
        widgets = {
            'DATE_OF_BIRTH': DateInput(attrs={'type': 'date'}),  # This will display a calendar picker
        }
        labels = {
            'HEIGHT': 'HEIGHT (in cm)',
            'WEIGHT': 'WEIGHT (in kg)',
        }

        
class RoleSelectionForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['role']

        
class PlayerForm(forms.ModelForm):
    position_played = forms.ChoiceField(choices=[], required=False)  # Update to ChoiceField

    class Meta:
        model = Profile
        fields = [
            'position_played', 
            'jersey_number', 
            'preferred_hand', 
            'previous_teams', 
            'preferred_league_level', 
            'medical_info', 
            'availability', 
            'preferred_coaches'
        ]
        labels = {
            'preferred_league_level': 'Preferred League Level (Amateur, Semi-pro, etc.)', 
            'availability': 'Availability (Availability for matches/practices)',
        }

    def __init__(self, *args, **kwargs):
        user_profile = kwargs.pop('user_profile', None)
        super().__init__(*args, **kwargs)

        if user_profile:
            self.fields['position_played'].choices = user_profile.get_position_choices()

        
class VolleyBallForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            'spike_height', 
            'block_height', 
            'serving_style', 
            'volleyball_achievements'
        ]
        labels = {
            'serving_style': 'Serving Style (Jump Serve, Float Serve, Underhand Serve, etc.)', 
        }

class BasketBallForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            'basketball_playing_style', 
            'vertical_leap', 
            'wingspan', 
            'basketball_achievements'
        ]
        labels = {
            'basketball_playing_style': 'Playing Style (Defensive, Offensive, All-rounder)', 
            'vertical_leap': 'Vertical Leap (In inches)',
            'wingspan': 'Wingspan (In inches)',
        }
