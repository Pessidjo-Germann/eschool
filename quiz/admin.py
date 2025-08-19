from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Quiz, Question, Choice, QuizAttempt, Answer


class ChoiceInline(admin.TabularInline):
    """Inline admin pour les choix de réponse"""
    model = Choice
    extra = 2
    fields = ['choice_text', 'is_correct', 'order', 'explanation']


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """Admin pour les questions"""
    list_display = ['quiz', 'question_text_short', 'question_type', 'points', 'order']
    list_filter = ['question_type', 'quiz__course', 'quiz']
    search_fields = ['question_text', 'quiz__title']
    ordering = ['quiz', 'order']
    inlines = [ChoiceInline]
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('quiz', 'question_text', 'question_type', 'points', 'order')
        }),
        ('Configuration avancée', {
            'fields': ('explanation', 'image'),
            'classes': ('collapse',)
        }),
        ('Questions numériques', {
            'fields': ('correct_number', 'tolerance'),
            'classes': ('collapse',)
        }),
        ('Questions texte', {
            'fields': ('correct_text', 'case_sensitive'),
            'classes': ('collapse',)
        }),
    )
    
    def question_text_short(self, obj):
        return obj.question_text[:50] + '...' if len(obj.question_text) > 50 else obj.question_text
    question_text_short.short_description = 'Question'


class QuestionInline(admin.StackedInline):
    """Inline admin pour les questions dans un quiz"""
    model = Question
    extra = 1
    fields = ['question_text', 'question_type', 'points', 'order']
    show_change_link = True


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    """Admin pour les quiz"""
    list_display = [
        'title', 'course', 'quiz_type', 'is_published', 
        'total_questions', 'total_attempts', 'created_at'
    ]
    list_filter = [
        'quiz_type', 'difficulty', 'is_published', 'is_required',
        'course__category', 'created_at'
    ]
    search_fields = ['title', 'description', 'course__title']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('title', 'description', 'course', 'lesson', 'instructor')
        }),
        ('Configuration du quiz', {
            'fields': (
                'quiz_type', 'difficulty', 'is_published', 'is_required'
            )
        }),
        ('Paramètres de tentative', {
            'fields': (
                'max_attempts', 'passing_score', 'time_limit'
            )
        }),
        ('Affichage et corrections', {
            'fields': (
                'randomize_questions', 'randomize_answers', 
                'show_correct_answers', 'show_score_immediately'
            ),
            'classes': ('collapse',)
        }),
        ('Disponibilité', {
            'fields': ('available_from', 'available_until'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [QuestionInline]
    
    def total_questions(self, obj):
        return obj.total_questions
    total_questions.short_description = 'Questions'
    
    def total_attempts(self, obj):
        count = obj.attempts.count()
        if count > 0:
            url = reverse('admin:quiz_quizattempt_changelist') + f'?quiz__id__exact={obj.id}'
            return format_html('<a href="{}">{}</a>', url, count)
        return count
    total_attempts.short_description = 'Tentatives'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Nouveau quiz
            obj.instructor = request.user
        super().save_model(request, obj, form, change)


class AnswerInline(admin.TabularInline):
    """Inline admin pour les réponses d'une tentative"""
    model = Answer
    extra = 0
    readonly_fields = ['question', 'is_correct', 'points_earned']
    fields = ['question', 'selected_choices', 'text_answer', 'numerical_answer', 'is_correct', 'points_earned']


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    """Admin pour les tentatives de quiz"""
    list_display = [
        'user', 'quiz', 'attempt_number', 'status', 'score', 
        'passed', 'started_at', 'time_taken'
    ]
    list_filter = [
        'status', 'passed', 'quiz__course', 'quiz',
        'started_at'
    ]
    search_fields = ['user__username', 'user__email', 'quiz__title']
    readonly_fields = [
        'id', 'attempt_number', 'started_at', 'time_taken',
        'expires_at', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'started_at'
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('id', 'quiz', 'user', 'attempt_number', 'status')
        }),
        ('Scores et résultats', {
            'fields': ('score', 'points_earned', 'total_points', 'passed')
        }),
        ('Gestion du temps', {
            'fields': ('started_at', 'submitted_at', 'time_taken', 'expires_at')
        }),
        ('Configuration et données', {
            'fields': ('questions_order', 'answers_data'),
            'classes': ('collapse',)
        }),
        ('Feedback', {
            'fields': ('feedback',),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [AnswerInline]
    
    actions = ['recalculate_scores']
    
    def recalculate_scores(self, request, queryset):
        """Action pour recalculer les scores des tentatives sélectionnées"""
        count = 0
        for attempt in queryset:
            if attempt.status in ['submitted', 'graded']:
                attempt.calculate_score()
                count += 1
        
        self.message_user(
            request,
            f'{count} tentative(s) recalculée(s) avec succès.'
        )
    recalculate_scores.short_description = 'Recalculer les scores'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('quiz', 'user')


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    """Admin pour les réponses individuelles"""
    list_display = [
        'attempt', 'question_short', 'answer_preview', 
        'is_correct', 'points_earned'
    ]
    list_filter = [
        'is_correct', 'question__question_type', 
        'attempt__quiz', 'attempt__status'
    ]
    search_fields = [
        'attempt__user__username', 'question__question_text',
        'text_answer'
    ]
    readonly_fields = ['is_correct', 'points_earned', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('attempt', 'question')
        }),
        ('Réponses', {
            'fields': ('selected_choices', 'text_answer', 'numerical_answer')
        }),
        ('Résultats', {
            'fields': ('is_correct', 'points_earned')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def question_short(self, obj):
        return f"Q{obj.question.order}: {obj.question.question_text[:30]}..."
    question_short.short_description = 'Question'
    
    def answer_preview(self, obj):
        if obj.selected_choices.exists():
            choices = obj.selected_choices.all()
            return f"Choix: {', '.join([c.choice_text[:20] for c in choices])}"
        elif obj.text_answer:
            return f"Texte: {obj.text_answer[:30]}..."
        elif obj.numerical_answer is not None:
            return f"Nombre: {obj.numerical_answer}"
        return "Aucune réponse"
    answer_preview.short_description = 'Réponse'


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    """Admin pour les choix (peut être utile pour les imports en masse)"""
    list_display = ['question', 'choice_text_short', 'is_correct', 'order']
    list_filter = ['is_correct', 'question__quiz', 'question__question_type']
    search_fields = ['choice_text', 'question__question_text']
    ordering = ['question', 'order']
    
    def choice_text_short(self, obj):
        return obj.choice_text[:50] + '...' if len(obj.choice_text) > 50 else obj.choice_text
    choice_text_short.short_description = 'Texte du choix'
