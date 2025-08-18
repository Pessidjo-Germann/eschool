from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from datetime import date
from .models import User, StudentProfile, InstructorProfile, AdminProfile


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=User.USER_ROLES, required=True)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'password1', 'password2')
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Cette adresse email est déjà utilisée.")
        return email


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'phone_number', 
            'date_of_birth', 'profile_picture', 'bio'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 4}),
            'profile_picture': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }
    
    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob and dob > date.today():
            raise ValidationError("La date de naissance ne peut pas être dans le futur.")
        return dob
    
    def clean_profile_picture(self):
        picture = self.cleaned_data.get('profile_picture')
        if picture:
            if picture.size > 5 * 1024 * 1024:  # 5MB limit
                raise ValidationError("La taille de l'image ne peut pas dépasser 5MB.")
            
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif']
            if not any(picture.name.lower().endswith(ext) for ext in valid_extensions):
                raise ValidationError("Format d'image non supporté. Utilisez JPG, PNG ou GIF.")
        
        return picture


class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = [
            'current_grade', 'parent_contact', 'emergency_contact', 
            'address', 'academic_year'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean_parent_contact(self):
        contact = self.cleaned_data.get('parent_contact')
        if contact and not contact.replace('+', '').replace(' ', '').replace('-', '').isdigit():
            raise ValidationError("Le numéro de contact doit contenir uniquement des chiffres.")
        return contact
    
    def clean_emergency_contact(self):
        contact = self.cleaned_data.get('emergency_contact')
        if contact and not contact.replace('+', '').replace(' ', '').replace('-', '').isdigit():
            raise ValidationError("Le numéro d'urgence doit contenir uniquement des chiffres.")
        return contact


class InstructorProfileForm(forms.ModelForm):
    class Meta:
        model = InstructorProfile
        fields = [
            'department', 'office_location', 'office_hours', 'research_interests'
        ]
        widgets = {
            'office_hours': forms.Textarea(attrs={'rows': 3}),
            'research_interests': forms.Textarea(attrs={'rows': 4}),
        }


class AdminProfileForm(forms.ModelForm):
    class Meta:
        model = AdminProfile
        fields = ['permission_level', 'department', 'responsibilities']
        widgets = {
            'responsibilities': forms.Textarea(attrs={'rows': 4}),
        }


class InstructorQualificationsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['qualifications', 'experience_years', 'specialization']
        widgets = {
            'qualifications': forms.Textarea(attrs={'rows': 4}),
        }
    
    def clean_experience_years(self):
        years = self.cleaned_data.get('experience_years')
        if years is not None and years < 0:
            raise ValidationError("Les années d'expérience ne peuvent pas être négatives.")
        if years is not None and years > 50:
            raise ValidationError("Les années d'expérience semblent trop élevées.")
        return years


class ProfilePictureForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['profile_picture']
        widgets = {
            'profile_picture': forms.ClearableFileInput(attrs={
                'accept': 'image/*',
                'class': 'form-control'
            }),
        }
    
    def clean_profile_picture(self):
        picture = self.cleaned_data.get('profile_picture')
        if picture:
            if picture.size > 5 * 1024 * 1024:  # 5MB limit
                raise ValidationError("La taille de l'image ne peut pas dépasser 5MB.")
            
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif']
            if not any(picture.name.lower().endswith(ext) for ext in valid_extensions):
                raise ValidationError("Format d'image non supporté. Utilisez JPG, PNG ou GIF.")
                
            # Check image dimensions
            try:
                from PIL import Image
                img = Image.open(picture)
                if img.width < 100 or img.height < 100:
                    raise ValidationError("L'image doit faire au moins 100x100 pixels.")
            except Exception:
                raise ValidationError("Fichier image invalide.")
        
        return picture