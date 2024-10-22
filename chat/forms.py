from django.forms import ModelForm
from django import forms
from .models import *

class ChatmessageCreateForm(ModelForm):
    class Meta:
        model = GroupMessage
        fields = ['body']
        widgets = {
            'body': forms.TextInput(attrs={'placeholder': 'Add message ...', 'class': 'p-4 text-black', 'maxlength': '300', 'autofocus': True}),
        }


class NewGroupForm(ModelForm):
    team = forms.ModelChoiceField(
        queryset=Team.objects.none(),  # Start with an empty queryset
        widget=forms.Select(attrs={
            'class': 'p-4 text-black',
        }),
        required=True,  # Set to True to make team selection mandatory
        label="Select Team"
    )

    class Meta:
        model = ChatGroup
        fields = ['groupchat_name', 'team']  # Include team in the fields
        widgets = {
            'groupchat_name': forms.TextInput(attrs={
                'placeholder': 'Add name ...',
                'class': 'p-4 text-black',
                'maxlength': '300',
                'autofocus': 'True',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        # Expecting the user object to be passed to the form
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # Filter teams based on the current user's coaching role
            self.fields['team'].queryset = Team.objects.filter(COACH_ID=user)


class ChatRoomEditForm(ModelForm):
    class Meta:
        model = ChatGroup
        fields = ['groupchat_name']
        widgets = {
            'groupchat_name': forms.TextInput(attrs={
                'class': 'p-4 text-xl font-bold mb-4',
                'maxlength': '300',
                }),
        }

