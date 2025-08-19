from django import forms
from django.core.exceptions import ValidationError
from .models import Quiz, Question, Choice
from courses.models import Course, Lesson
import json


class QuizForm(forms.ModelForm):
    """Formulaire de création/modification de quiz"""
    
    class Meta:
        model = Quiz
        fields = [
            'title', 'description', 'course', 'lesson', 'quiz_type', 'difficulty',
            'time_limit', 'max_attempts', 'passing_score', 'randomize_questions',
            'randomize_answers', 'show_correct_answers', 'show_score_immediately',
            'is_published', 'is_required', 'available_from', 'available_until'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Titre du quiz'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Description du quiz'
            }),
            'course': forms.Select(attrs={'class': 'form-select'}),
            'lesson': forms.Select(attrs={'class': 'form-select'}),
            'quiz_type': forms.Select(attrs={'class': 'form-select'}),
            'difficulty': forms.Select(attrs={'class': 'form-select'}),
            'time_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': 'Durée en minutes'
            }),
            'max_attempts': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 10,
                'value': 1
            }),
            'passing_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 100,
                'value': 70
            }),
            'available_from': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'available_until': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'randomize_questions': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'randomize_answers': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_correct_answers': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_score_immediately': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filtrer les cours pour l'instructeur connecté
        if user and user.role == 'instructor':
            self.fields['course'].queryset = Course.objects.filter(instructor=user)
            self.fields['lesson'].queryset = Lesson.objects.none()  # Sera peuplé via AJAX
        
        # Personnaliser les labels
        self.fields['time_limit'].help_text = "Laisser vide pour un temps illimité"
        self.fields['available_from'].help_text = "Laisser vide pour disponibilité immédiate"
        self.fields['available_until'].help_text = "Laisser vide pour pas de limite"
    
    def clean(self):
        cleaned_data = super().clean()
        available_from = cleaned_data.get('available_from')
        available_until = cleaned_data.get('available_until')
        
        if available_from and available_until and available_from >= available_until:
            raise ValidationError("La date de fin doit être postérieure à la date de début")
        
        return cleaned_data


class QuestionForm(forms.ModelForm):
    """Formulaire pour les questions de quiz"""
    
    class Meta:
        model = Question
        fields = [
            'question_text', 'question_type', 'points', 'order',
            'explanation', 'image', 'correct_number', 'tolerance',
            'correct_text', 'case_sensitive'
        ]
        widgets = {
            'question_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Saisissez votre question...'
            }),
            'question_type': forms.Select(attrs={'class': 'form-select'}),
            'points': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'value': 1
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1
            }),
            'explanation': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Explication optionnelle...'
            }),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'correct_number': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': 'any',
                'placeholder': 'Réponse numérique correcte'
            }),
            'tolerance': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': 'any',
                'value': 0.1,
                'placeholder': 'Tolérance'
            }),
            'correct_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Réponses acceptées (une par ligne)'
            }),
            'case_sensitive': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ChoiceForm(forms.ModelForm):
    """Formulaire pour les choix de réponse"""
    
    class Meta:
        model = Choice
        fields = ['choice_text', 'is_correct', 'order', 'explanation']
        widgets = {
            'choice_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Texte du choix'
            }),
            'is_correct': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1
            }),
            'explanation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Explication optionnelle'
            }),
        }


class QuizBulkCreateForm(forms.Form):
    """Formulaire pour la création en masse de questions via JSON/CSV"""
    
    FORMAT_CHOICES = [
        ('json', 'Format JSON'),
        ('csv', 'Format CSV'),
    ]
    
    format_type = forms.ChoiceField(
        choices=FORMAT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    data = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 15,
            'placeholder': 'Collez vos données ici...'
        }),
        help_text="Format JSON ou CSV selon votre choix"
    )
    
    def clean_data(self):
        data = self.cleaned_data['data']
        format_type = self.cleaned_data.get('format_type')
        
        if format_type == 'json':
            try:
                parsed_data = json.loads(data)
                if not isinstance(parsed_data, list):
                    raise ValidationError("Le JSON doit être une liste de questions")
                return parsed_data
            except json.JSONDecodeError:
                raise ValidationError("Format JSON invalide")
        
        elif format_type == 'csv':
            # Validation basique CSV
            lines = data.strip().split('\n')
            if len(lines) < 2:
                raise ValidationError("Le CSV doit contenir au moins une ligne d'en-tête et une ligne de données")
            return data
        
        return data


class QuizSettingsForm(forms.ModelForm):
    """Formulaire pour les paramètres avancés du quiz"""
    
    class Meta:
        model = Quiz
        fields = [
            'randomize_questions', 'randomize_answers', 'show_correct_answers',
            'show_score_immediately', 'is_published', 'is_required'
        ]
        widgets = {
            'randomize_questions': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'randomize_answers': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_correct_answers': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_score_immediately': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# Formsets pour la gestion dynamique des choix
from django.forms import inlineformset_factory

ChoiceFormSet = inlineformset_factory(
    Question, 
    Choice, 
    form=ChoiceForm,
    extra=2,  # 2 choix par défaut
    min_num=2,  # Minimum 2 choix
    max_num=6,  # Maximum 6 choix
    can_delete=True
)


class QuizPreviewForm(forms.Form):
    """Formulaire pour configurer la prévisualisation"""
    
    show_answers = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Afficher les réponses correctes dans l'aperçu"
    )
    
    show_explanations = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Afficher les explications dans l'aperçu"
    )
    
    randomize_preview = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Appliquer la randomisation dans l'aperçu"
    )


class QuizDuplicateForm(forms.Form):
    """Formulaire pour dupliquer un quiz"""
    
    new_title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nouveau titre pour la copie'
        })
    )
    
    new_course = forms.ModelChoiceField(
        queryset=Course.objects.none(),
        required=False,
        empty_label="Même cours",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    copy_questions = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Copier toutes les questions"
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user and user.role == 'instructor':
            self.fields['new_course'].queryset = Course.objects.filter(instructor=user)


class QuestionImportForm(forms.Form):
    """Formulaire pour importer des questions depuis un autre quiz"""
    
    source_quiz = forms.ModelChoiceField(
        queryset=Quiz.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Choisir le quiz source"
    )
    
    questions = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        help_text="Sélectionner les questions à importer"
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        target_quiz = kwargs.pop('target_quiz', None)
        super().__init__(*args, **kwargs)
        
        if user and user.role == 'instructor':
            # Exclure le quiz cible de la liste
            queryset = Quiz.objects.filter(instructor=user)
            if target_quiz:
                queryset = queryset.exclude(id=target_quiz.id)
            self.fields['source_quiz'].queryset = queryset
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        target_quiz = kwargs.pop('target_quiz', None)
        super().__init__(*args, **kwargs)
        
        if user and user.role == 'instructor':
            queryset = Quiz.objects.filter(instructor=user)
            if target_quiz:
                queryset = queryset.exclude(id=target_quiz.id)
            self.fields['source_quiz'].queryset = queryset
        
        # Les choix de questions seront peuplés via AJAX


class QuizAnalyticsFilterForm(forms.Form):
    """Formulaire de filtrage pour les analytics"""
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'Tous les statuts')] + [
            ('submitted', 'Soumises'),
            ('graded', 'Notées'),
            ('expired', 'Expirées'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    passed = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'Tous'),
            ('true', 'Réussis'),
            ('false', 'Échoués'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )