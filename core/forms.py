from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordResetForm, SetPasswordForm
from users.models import User


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
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

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("Un utilisateur avec cette adresse email existe déjà.")
        return email


class CustomPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={
            'class': 'form-control modern-input',
            'placeholder': 'Adresse email'
        })
    )


class CustomSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control modern-input',
            'placeholder': 'Nouveau mot de passe'
        })
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control modern-input',
            'placeholder': 'Confirmer le nouveau mot de passe'
        })
    )
