from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from courses.models import Course, Lesson
import uuid
import json

User = get_user_model()


class Quiz(models.Model):
    """Modèle principal pour les quiz/évaluations"""
    
    QUIZ_TYPES = [
        ('lesson', 'Quiz de leçon'),
        ('module', 'Quiz de module'),
        ('final', 'Examen final'),
        ('practice', 'Quiz d\'entraînement'),
    ]
    
    DIFFICULTY_LEVELS = [
        ('beginner', 'Débutant'),
        ('intermediate', 'Intermédiaire'),
        ('advanced', 'Avancé'),
        ('expert', 'Expert'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, verbose_name="Titre")
    description = models.TextField(blank=True, verbose_name="Description")
    
    # Relations
    course = models.ForeignKey(
        Course, 
        on_delete=models.CASCADE, 
        related_name='quizzes',
        verbose_name="Cours"
    )
    lesson = models.ForeignKey(
        Lesson, 
        on_delete=models.CASCADE, 
        related_name='quizzes',
        blank=True, 
        null=True,
        verbose_name="Leçon"
    )
    instructor = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='created_quizzes',
        verbose_name="Instructeur"
    )
    
    # Configuration du quiz
    quiz_type = models.CharField(
        max_length=20, 
        choices=QUIZ_TYPES, 
        default='lesson',
        verbose_name="Type de quiz"
    )
    difficulty = models.CharField(
        max_length=20, 
        choices=DIFFICULTY_LEVELS, 
        default='beginner',
        verbose_name="Niveau de difficulté"
    )
    
    # Paramètres temporels
    time_limit = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Durée en minutes (laisser vide pour illimité)",
        verbose_name="Limite de temps"
    )
    
    # Paramètres d'accès et tentatives
    max_attempts = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Nombre maximum de tentatives autorisées",
        verbose_name="Tentatives maximum"
    )
    passing_score = models.PositiveIntegerField(
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Score minimum pour réussir (en pourcentage)",
        verbose_name="Score de passage"
    )
    
    # Configuration d'affichage
    randomize_questions = models.BooleanField(
        default=False,
        help_text="Mélanger l'ordre des questions",
        verbose_name="Questions aléatoires"
    )
    randomize_answers = models.BooleanField(
        default=False,
        help_text="Mélanger l'ordre des réponses",
        verbose_name="Réponses aléatoires"
    )
    show_correct_answers = models.BooleanField(
        default=True,
        help_text="Afficher les bonnes réponses après la tentative",
        verbose_name="Afficher les corrections"
    )
    show_score_immediately = models.BooleanField(
        default=True,
        help_text="Afficher le score immédiatement après soumission",
        verbose_name="Score immédiat"
    )
    
    # Publication et statut
    is_published = models.BooleanField(default=False, verbose_name="Publié")
    is_required = models.BooleanField(
        default=False,
        help_text="Quiz obligatoire pour la progression",
        verbose_name="Obligatoire"
    )
    
    # Dates
    available_from = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Date/heure d'ouverture du quiz",
        verbose_name="Disponible à partir de"
    )
    available_until = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Date/heure de fermeture du quiz",
        verbose_name="Disponible jusqu'à"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Quiz"
        verbose_name_plural = "Quiz"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.course.title})"
    
    @property
    def total_questions(self):
        """Nombre total de questions dans le quiz"""
        return self.questions.count()
    
    @property
    def total_points(self):
        """Score total possible du quiz"""
        return sum(q.points for q in self.questions.all())
    
    def is_available(self):
        """Vérifie si le quiz est actuellement disponible"""
        now = timezone.now()
        if self.available_from and now < self.available_from:
            return False
        if self.available_until and now > self.available_until:
            return False
        return True
    
    def can_user_take_quiz(self, user):
        """Vérifie si un utilisateur peut passer le quiz"""
        if not self.is_published or not self.is_available():
            return False, "Quiz non disponible"
        
        attempts_count = self.attempts.filter(user=user).count()
        if attempts_count >= self.max_attempts:
            return False, f"Limite de {self.max_attempts} tentative(s) atteinte"
        
        return True, "Quiz disponible"
    
    def is_available_for_student(self, user):
        """Vérifie si un étudiant a accès à ce quiz"""
        # Vérifier que l'étudiant est inscrit au cours
        from courses.models import Enrollment
        if not Enrollment.objects.filter(user=user, course=self.course).exists():
            return False
        
        # Vérifier que le quiz est publié et disponible
        if not self.is_published or not self.is_available():
            return False
        
        return True


class Question(models.Model):
    """Modèle pour les questions des quiz"""
    
    QUESTION_TYPES = [
        ('multiple_choice', 'QCM (choix multiple)'),
        ('single_choice', 'QCU (choix unique)'),
        ('true_false', 'Vrai/Faux'),
        ('short_answer', 'Réponse courte'),
        ('essay', 'Question ouverte'),
        ('numerical', 'Réponse numérique'),
        ('matching', 'Appariement'),
        ('ordering', 'Classement'),
    ]
    
    quiz = models.ForeignKey(
        Quiz, 
        on_delete=models.CASCADE, 
        related_name='questions',
        verbose_name="Quiz"
    )
    question_text = models.TextField(verbose_name="Texte de la question")
    question_type = models.CharField(
        max_length=20, 
        choices=QUESTION_TYPES,
        verbose_name="Type de question"
    )
    
    # Configuration de la question
    points = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Points"
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Ordre d'affichage de la question",
        verbose_name="Ordre"
    )
    
    # Paramètres spéciaux
    explanation = models.TextField(
        blank=True,
        help_text="Explication affichée après la réponse",
        verbose_name="Explication"
    )
    image = models.ImageField(
        upload_to='quiz/questions/',
        blank=True,
        null=True,
        verbose_name="Image"
    )
    
    # Pour les questions numériques
    correct_number = models.FloatField(
        null=True, 
        blank=True,
        help_text="Réponse numérique correcte",
        verbose_name="Réponse numérique"
    )
    tolerance = models.FloatField(
        null=True, 
        blank=True, 
        default=0.1,
        help_text="Tolérance pour les réponses numériques",
        verbose_name="Tolérance"
    )
    
    # Pour les questions à réponse courte
    correct_text = models.TextField(
        blank=True,
        help_text="Réponse texte correcte (une réponse par ligne)",
        verbose_name="Réponse texte"
    )
    case_sensitive = models.BooleanField(
        default=False,
        help_text="La casse est-elle importante pour la réponse ?",
        verbose_name="Sensible à la casse"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Question"
        verbose_name_plural = "Questions"
        ordering = ['quiz', 'order', 'id']
        unique_together = ['quiz', 'order']
    
    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}..."
    
    @property
    def correct_choices(self):
        """Retourne les choix corrects pour cette question"""
        return self.choices.filter(is_correct=True)
    
    def get_correct_text_answers(self):
        """Retourne la liste des réponses texte correctes"""
        if self.correct_text:
            return [answer.strip() for answer in self.correct_text.split('\n') if answer.strip()]
        return []
    
    def check_answer(self, user_answer):
        """Vérifie si une réponse utilisateur est correcte"""
        if self.question_type in ['multiple_choice', 'single_choice']:
            if isinstance(user_answer, list):
                correct_ids = set(self.correct_choices.values_list('id', flat=True))
                user_ids = set(user_answer)
                return correct_ids == user_ids
            else:
                return self.choices.filter(id=user_answer, is_correct=True).exists()
        
        elif self.question_type == 'true_false':
            correct_choice = self.correct_choices.first()
            return correct_choice and str(correct_choice.id) == str(user_answer)
        
        elif self.question_type == 'numerical':
            try:
                user_num = float(user_answer)
                return abs(user_num - self.correct_number) <= self.tolerance
            except (ValueError, TypeError):
                return False
        
        elif self.question_type == 'short_answer':
            correct_answers = self.get_correct_text_answers()
            user_text = str(user_answer).strip()
            
            if not self.case_sensitive:
                user_text = user_text.lower()
                correct_answers = [ans.lower() for ans in correct_answers]
            
            return user_text in correct_answers
        
        return False


class Choice(models.Model):
    """Modèle pour les choix de réponse des questions QCM/QCU/Vrai-Faux"""
    
    question = models.ForeignKey(
        Question, 
        on_delete=models.CASCADE, 
        related_name='choices',
        verbose_name="Question"
    )
    choice_text = models.TextField(verbose_name="Texte du choix")
    is_correct = models.BooleanField(default=False, verbose_name="Réponse correcte")
    order = models.PositiveIntegerField(
        default=0,
        help_text="Ordre d'affichage du choix",
        verbose_name="Ordre"
    )
    explanation = models.TextField(
        blank=True,
        help_text="Explication pour ce choix",
        verbose_name="Explication"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Choix"
        verbose_name_plural = "Choix"
        ordering = ['question', 'order', 'id']
        unique_together = ['question', 'order']
    
    def __str__(self):
        return f"{self.choice_text[:30]}... ({'✓' if self.is_correct else '✗'})"


class QuizAttempt(models.Model):
    """Modèle pour les tentatives de quiz des utilisateurs"""
    
    STATUS_CHOICES = [
        ('in_progress', 'En cours'),
        ('submitted', 'Soumise'),
        ('graded', 'Notée'),
        ('expired', 'Expirée'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(
        Quiz, 
        on_delete=models.CASCADE, 
        related_name='attempts',
        verbose_name="Quiz"
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='quiz_attempts',
        verbose_name="Utilisateur"
    )
    
    # État de la tentative
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='in_progress',
        verbose_name="Statut"
    )
    attempt_number = models.PositiveIntegerField(
        verbose_name="Numéro de tentative"
    )
    
    # Scores et résultats
    score = models.FloatField(
        null=True, 
        blank=True,
        help_text="Score obtenu (en pourcentage)",
        verbose_name="Score"
    )
    points_earned = models.PositiveIntegerField(
        default=0,
        verbose_name="Points obtenus"
    )
    total_points = models.PositiveIntegerField(
        default=0,
        verbose_name="Total des points"
    )
    
    # Gestion du temps
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Commencée à")
    submitted_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="Soumise à"
    )
    time_taken = models.DurationField(
        null=True, 
        blank=True,
        help_text="Temps pris pour compléter le quiz",
        verbose_name="Temps pris"
    )
    expires_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Date d'expiration si limite de temps",
        verbose_name="Expire à"
    )
    
    # Configuration pour cette tentative
    questions_order = models.TextField(
        help_text="Ordre des questions pour cette tentative (JSON)",
        verbose_name="Ordre des questions"
    )
    answers_data = models.TextField(
        default='{}',
        help_text="Données des réponses (JSON)",
        verbose_name="Données des réponses"
    )
    
    # Feedback
    passed = models.BooleanField(default=False, verbose_name="Réussi")
    feedback = models.TextField(
        blank=True,
        help_text="Feedback personnalisé de l'instructeur",
        verbose_name="Commentaire"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Tentative de quiz"
        verbose_name_plural = "Tentatives de quiz"
        ordering = ['-started_at']
        unique_together = ['quiz', 'user', 'attempt_number']
    
    def __str__(self):
        return f"{self.user.username} - {self.quiz.title} (Tentative {self.attempt_number})"
    
    def save(self, *args, **kwargs):
        # Auto-assign attempt number
        if not self.attempt_number:
            last_attempt = QuizAttempt.objects.filter(
                quiz=self.quiz, 
                user=self.user
            ).order_by('-attempt_number').first()
            self.attempt_number = (last_attempt.attempt_number + 1) if last_attempt else 1
        
        # Set expiration time if quiz has time limit
        if not self.expires_at and self.quiz.time_limit:
            self.expires_at = self.started_at + timezone.timedelta(minutes=self.quiz.time_limit)
        
        super().save(*args, **kwargs)
    
    def get_questions_order(self):
        """Retourne l'ordre des questions pour cette tentative"""
        try:
            return json.loads(self.questions_order)
        except (json.JSONDecodeError, TypeError):
            return []
    
    def set_questions_order(self, questions_list):
        """Définit l'ordre des questions pour cette tentative"""
        self.questions_order = json.dumps(questions_list)
    
    def get_answers_data(self):
        """Retourne les données des réponses"""
        try:
            return json.loads(self.answers_data)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_answers_data(self, answers_dict):
        """Définit les données des réponses"""
        self.answers_data = json.dumps(answers_dict)
    
    def is_expired(self):
        """Vérifie si la tentative a expiré"""
        if self.status != 'in_progress':
            return False
        return self.expires_at and timezone.now() > self.expires_at
    
    def get_time_remaining(self):
        """Retourne le temps restant en secondes"""
        if not self.expires_at or self.status != 'in_progress':
            return None
        remaining = self.expires_at - timezone.now()
        return max(0, int(remaining.total_seconds()))
    
    def calculate_score(self):
        """Calcule automatiquement le score de la tentative"""
        if self.status not in ['submitted', 'graded']:
            return
        
        total_points = 0
        earned_points = 0
        answers = self.get_answers_data()
        
        for question in self.quiz.questions.all():
            total_points += question.points
            question_id = str(question.id)
            
            if question_id in answers:
                user_answer = answers[question_id]
                if question.check_answer(user_answer):
                    earned_points += question.points
        
        self.total_points = total_points
        self.points_earned = earned_points
        self.score = (earned_points / total_points * 100) if total_points > 0 else 0
        self.passed = self.score >= self.quiz.passing_score
        
        if self.status == 'submitted':
            self.status = 'graded'
        
        self.save()
    
    def submit_attempt(self):
        """Soumet la tentative et calcule le score"""
        if self.status != 'in_progress':
            return False
        
        self.submitted_at = timezone.now()
        self.time_taken = self.submitted_at - self.started_at
        self.status = 'submitted'
        self.save()
        
        # Calculate score automatically
        self.calculate_score()
        return True


class Answer(models.Model):
    """Modèle pour stocker les réponses individuelles aux questions"""
    
    attempt = models.ForeignKey(
        QuizAttempt, 
        on_delete=models.CASCADE, 
        related_name='answers',
        verbose_name="Tentative"
    )
    question = models.ForeignKey(
        Question, 
        on_delete=models.CASCADE, 
        related_name='user_answers',
        verbose_name="Question"
    )
    
    # Différents types de réponses possibles
    selected_choices = models.ManyToManyField(
        Choice, 
        blank=True,
        help_text="Choix sélectionnés pour QCM/QCU/Vrai-Faux",
        verbose_name="Choix sélectionnés"
    )
    text_answer = models.TextField(
        blank=True,
        help_text="Réponse textuelle pour questions ouvertes",
        verbose_name="Réponse texte"
    )
    numerical_answer = models.FloatField(
        null=True, 
        blank=True,
        help_text="Réponse numérique",
        verbose_name="Réponse numérique"
    )
    
    # Résultat de cette réponse
    is_correct = models.BooleanField(default=False, verbose_name="Correct")
    points_earned = models.PositiveIntegerField(default=0, verbose_name="Points obtenus")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Réponse"
        verbose_name_plural = "Réponses"
        unique_together = ['attempt', 'question']
    
    def __str__(self):
        return f"{self.attempt.user.username} - Q{self.question.order}"
    
    def save(self, *args, **kwargs):
        # Auto-check correctness and assign points
        self.check_correctness()
        super().save(*args, **kwargs)
    
    def check_correctness(self):
        """Vérifie automatiquement la correction de la réponse"""
        question = self.question
        
        if question.question_type in ['multiple_choice', 'single_choice', 'true_false']:
            selected_ids = list(self.selected_choices.values_list('id', flat=True))
            self.is_correct = question.check_answer(selected_ids)
        
        elif question.question_type == 'numerical':
            self.is_correct = question.check_answer(self.numerical_answer)
        
        elif question.question_type == 'short_answer':
            self.is_correct = question.check_answer(self.text_answer)
        
        # Assign points
        self.points_earned = question.points if self.is_correct else 0