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
        fields = ['image','FIRST_NAME', 'LAST_NAME','MIDDLE_NAME','DATE_OF_BIRTH','GENDER','ADDRESS', 'HEIGHT', 'WEIGHT', 'PHONE']
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