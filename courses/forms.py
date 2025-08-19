from django import forms
from django.core.exceptions import ValidationError
from .models import Course, Category, Tag, Module, Lesson, LessonResource


class CourseForm(forms.ModelForm):
    """Formulaire de création/modification de cours"""
    
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        widget=forms.CheckboxSelectMultiple(),
        required=False
    )
    
    class Meta:
        model = Course
        fields = [
            'title', 'short_description', 'description', 'category', 'tags',
            'difficulty', 'language', 'thumbnail', 'price', 'is_free',
            'prerequisites', 'learning_objectives', 'target_audience',
            'has_certificate'
        ]
        
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Titre du cours'
            }),
            'short_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description courte (300 caractères max)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': 'Description complète du cours'
            }),
            'difficulty': forms.Select(attrs={'class': 'form-select'}),
            'language': forms.Select(attrs={'class': 'form-select'}),
            'thumbnail': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'is_free': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'prerequisites': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Prérequis nécessaires'
            }),
            'learning_objectives': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Objectifs d\'apprentissage'
            }),
            'target_audience': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Public cible'
            }),
            'has_certificate': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def clean(self):
        cleaned_data = super().clean()
        price = cleaned_data.get('price')
        is_free = cleaned_data.get('is_free')
        
        # Validation cohérence prix/gratuité
        if is_free and price and price > 0:
            raise ValidationError("Un cours gratuit ne peut pas avoir un prix.")
        
        if not is_free and (not price or price <= 0):
            raise ValidationError("Un cours payant doit avoir un prix supérieur à 0.")
        
        return cleaned_data


class ModuleForm(forms.ModelForm):
    """Formulaire de création/modification de module"""
    
    class Meta:
        model = Module
        fields = [
            'title', 'description', 'order', 'is_published', 'is_free'
        ]
        
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Titre du module'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Description du module'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_free': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }


class LessonForm(forms.ModelForm):
    """Formulaire de création/modification de leçon"""
    
    class Meta:
        model = Lesson
        fields = [
            'title', 'description', 'content', 'lesson_type', 'order',
            'duration', 'video_url', 'video_file', 'audio_file', 
            'document_file', 'external_url', 'is_published', 
            'is_preview', 'is_mandatory', 'notes'
        ]
        
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Titre de la leçon'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description courte'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control editor',
                'rows': 10,
                'placeholder': 'Contenu de la leçon'
            }),
            'lesson_type': forms.Select(attrs={'class': 'form-select'}),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'duration': forms.TimeInput(attrs={
                'class': 'form-control',
                'placeholder': 'HH:MM:SS'
            }),
            'video_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'URL YouTube, Vimeo, etc.'
            }),
            'video_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'video/*'
            }),
            'audio_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'audio/*'
            }),
            'document_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.ppt,.pptx'
            }),
            'external_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'Lien externe'
            }),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_preview': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_mandatory': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Notes privées'
            })
        }
    
    def clean(self):
        cleaned_data = super().clean()
        lesson_type = cleaned_data.get('lesson_type')
        video_url = cleaned_data.get('video_url')
        video_file = cleaned_data.get('video_file')
        audio_file = cleaned_data.get('audio_file')
        document_file = cleaned_data.get('document_file')
        external_url = cleaned_data.get('external_url')
        content = cleaned_data.get('content')
        
        # Validation selon le type de leçon
        if lesson_type == 'video' and not video_url and not video_file:
            raise ValidationError("Une leçon vidéo doit avoir une URL ou un fichier vidéo.")
        
        if lesson_type == 'audio' and not audio_file:
            raise ValidationError("Une leçon audio doit avoir un fichier audio.")
        
        if lesson_type == 'document' and not document_file:
            raise ValidationError("Une leçon document doit avoir un fichier document.")
        
        if lesson_type == 'external' and not external_url:
            raise ValidationError("Une leçon externe doit avoir une URL externe.")
        
        if lesson_type == 'text' and not content:
            raise ValidationError("Une leçon texte doit avoir du contenu.")
        
        return cleaned_data


class LessonResourceForm(forms.ModelForm):
    """Formulaire pour les ressources de leçon"""
    
    class Meta:
        model = LessonResource
        fields = [
            'title', 'description', 'resource_type', 'file', 'url',
            'is_downloadable', 'order'
        ]
        
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Titre de la ressource'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description'
            }),
            'resource_type': forms.Select(attrs={'class': 'form-select'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'URL de la ressource'
            }),
            'is_downloadable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            })
        }
    
    def clean(self):
        cleaned_data = super().clean()
        file = cleaned_data.get('file')
        url = cleaned_data.get('url')
        
        if not file and not url:
            raise ValidationError("Veuillez fournir un fichier ou une URL.")
        
        if file and url:
            raise ValidationError("Veuillez choisir soit un fichier, soit une URL, pas les deux.")
        
        return cleaned_data


class BulkModuleForm(forms.Form):
    """Formulaire pour créer plusieurs modules en lot"""
    
    modules = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 10,
            'placeholder': 'Un module par ligne\nModule 1: Introduction\nModule 2: Concepts de base\n...'
        }),
        help_text="Un module par ligne. Format: Titre du module ou Titre: Description"
    )
    
    start_order = forms.IntegerField(
        initial=1,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Numéro d'ordre de départ"
    )
    
    is_published = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Publier les modules créés"
    )


class CourseSettingsForm(forms.ModelForm):
    """Formulaire pour les paramètres avancés du cours"""
    
    class Meta:
        model = Course
        fields = [
            'meta_description', 'meta_keywords', 'status'
        ]
        
        widgets = {
            'meta_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description SEO (160 caractères max)'
            }),
            'meta_keywords': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Mots-clés séparés par des virgules'
            }),
            'status': forms.Select(attrs={'class': 'form-select'})
        }