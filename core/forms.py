from django import forms
from django.contrib.auth.forms import UserCreationForm
from users.models import User


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control modern-input',
            'placeholder': 'Email'
        })
    )
    
    first_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control modern-input',
            'placeholder': 'Prénom'
        })
    )
    
    last_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control modern-input',
            'placeholder': 'Nom'
        })
    )
    
    role = forms.ChoiceField(
        choices=User.USER_ROLES,
        initial='student',
        widget=forms.Select(attrs={
            'class': 'form-select modern-input'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'role', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Customize form field widgets
        self.fields['username'].widget.attrs.update({
            'class': 'form-control modern-input',
            'placeholder': 'Nom d\'utilisateur'
        })
        
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control modern-input',
            'placeholder': 'Mot de passe'
        })
        
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control modern-input',
            'placeholder': 'Confirmer le mot de passe'
        })

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.role = self.cleaned_data['role']
        
        if commit:
            user.save()
        return user
