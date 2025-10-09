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
        },
        required=False  # Allow this field to be optional
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
    
    PREFERRED_LEAGUE_LEVEL_CHOICES = [
    ('amateur', 'Amateur'),
    ('semi_pro', 'Semi-pro'),
    ('professional', 'Professional'),
    # Add other league levels as needed
]
    preferred_league_level = forms.ChoiceField(choices=PREFERRED_LEAGUE_LEVEL_CHOICES)  
        
    class Meta:
        model = Profile
        fields = [
            'preferred_league_level', 
            'medical_info', 
            'availability', 
            'preferred_coaches'
        ]
        labels = {
            'preferred_league_level': 'Preferred League Level (Amateur, Semi-pro, etc.)', 
            'availability': 'Availability (Availability for matches/practices)',
        }


class VolleyBallForm(forms.ModelForm):
    
    PREFERRED_HAND_CHOICES = [
    ('left', 'Left'),
    ('right', 'Right'),
    ]
    
    SERVING_STYLE_CHOICES = [
        ('jump_serve', 'Jump Serve'),
        ('float_serve', 'Float Serve'),
        ('underhand_serve', 'Underhand Serve'),
        # Add other serving styles as needed
    ]
    
    preferred_hand = forms.ChoiceField(choices=PREFERRED_HAND_CHOICES)
    volleyball_position_played = forms.ChoiceField(choices=Profile.VOLLEYBALL_POSITIONS, required=False)
    serving_style = forms.ChoiceField(choices=SERVING_STYLE_CHOICES)

    class Meta:
        model = Profile
        fields = [
            'volleyball_position_played',
            'volleyball_jersey_number', 
            'preferred_hand', 
            'volleyball_previous_teams', 
            'spike_height', 
            'block_height', 
            'serving_style', 
            'volleyball_achievements'
        ]
        labels = {
            'serving_style': 'Serving Style (Jump Serve, Float Serve, Underhand Serve, etc.)', 
        }


class BasketBallForm(forms.ModelForm):
    
    PREFERRED_HAND_CHOICES = [
    ('left', 'Left'),
    ('right', 'Right'),
    ]
    
    BASKETBALL_PLAYING_STYLE_CHOICES = [
        ('defensive', 'Defensive'),
        ('offensive', 'Offensive'),
        ('all_rounder', 'All-rounder'),
        # Add other styles as needed
    ]
    
    preferred_hand = forms.ChoiceField(choices=PREFERRED_HAND_CHOICES)
    basketball_position_played = forms.ChoiceField(choices=Profile.BASKETBALL_POSITIONS, required=False)
    basketball_playing_style = forms.ChoiceField(choices=BASKETBALL_PLAYING_STYLE_CHOICES)

    class Meta:
        model = Profile
        fields = [
            'basketball_position_played',
            'basketball_jersey_number', 
            'preferred_hand', 
            'basketball_previous_teams', 
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