from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
from django.utils.text import slugify
from users.models import User
import uuid


class Category(models.Model):
    """Catégories pour organiser les cours"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Nom")
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True, verbose_name="Description")
    icon = models.CharField(
        max_length=50, 
        blank=True, 
        help_text="Classe Bootstrap Icons (ex: bi-book, bi-code-slash)",
        verbose_name="Icône"
    )
    color = models.CharField(
        max_length=7,
        default="#007bff",
        help_text="Couleur hexadécimale (#RRGGBB)",
        verbose_name="Couleur"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories',
        verbose_name="Catégorie parente"
    )
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre d'affichage")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ['order', 'name']
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def get_all_courses_count(self):
        """Retourne le nombre total de cours dans cette catégorie et ses sous-catégories"""
        count = self.courses.filter(status='published').count()
        for subcategory in self.subcategories.all():
            count += subcategory.get_all_courses_count()
        return count


class Course(models.Model):
    """Modèle principal pour les cours"""
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('published', 'Publié'),
        ('archived', 'Archivé'),
        ('review', 'En révision'),
    ]
    
    DIFFICULTY_CHOICES = [
        ('beginner', 'Débutant'),
        ('intermediate', 'Intermédiaire'),
        ('advanced', 'Avancé'),
        ('expert', 'Expert'),
    ]
    
    LANGUAGE_CHOICES = [
        ('fr', 'Français'),
        ('en', 'Anglais'),
        ('es', 'Espagnol'),
        ('de', 'Allemand'),
    ]
    
    # Identifiants
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, verbose_name="Titre")
    slug = models.SlugField(max_length=250, unique=True, blank=True)
    
    # Métadonnées de base
    description = models.TextField(verbose_name="Description")
    short_description = models.CharField(
        max_length=300, 
        blank=True,
        help_text="Description courte pour les listes",
        verbose_name="Description courte"
    )
    
    # Médias
    thumbnail = models.ImageField(
        upload_to='courses/thumbnails/', 
        blank=True, 
        null=True,
        verbose_name="Image de couverture"
    )
    video_intro = models.URLField(
        blank=True,
        help_text="URL vers une vidéo d'introduction (YouTube, Vimeo, etc.)",
        verbose_name="Vidéo d'introduction"
    )
    
    # Catégorisation
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='courses',
        verbose_name="Catégorie"
    )
    tags = models.ManyToManyField(
        'Tag',
        blank=True,
        related_name='courses',
        verbose_name="Mots-clés"
    )
    
    # Instructeurs
    instructor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'instructor'},
        related_name='created_courses',
        verbose_name="Instructeur principal"
    )
    co_instructors = models.ManyToManyField(
        User,
        blank=True,
        limit_choices_to={'role': 'instructor'},
        related_name='co_created_courses',
        verbose_name="Co-instructeurs"
    )
    
    # Paramètres du cours
    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default='beginner',
        verbose_name="Niveau de difficulté"
    )
    language = models.CharField(
        max_length=2,
        choices=LANGUAGE_CHOICES,
        default='fr',
        verbose_name="Langue"
    )
    
    # Durée et planning
    estimated_duration = models.DurationField(
        blank=True,
        null=True,
        help_text="Durée estimée totale du cours",
        verbose_name="Durée estimée"
    )
    max_students = models.PositiveIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1)],
        help_text="Nombre maximum d'étudiants (laisser vide pour illimité)",
        verbose_name="Nombre max d'étudiants"
    )
    
    # Prix et monétisation
    is_free = models.BooleanField(default=True, verbose_name="Gratuit")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
        verbose_name="Prix"
    )
    currency = models.CharField(max_length=3, default='XAF', verbose_name="Devise")
    
    # Prérequis et objectifs
    prerequisites = models.TextField(
        blank=True,
        help_text="Connaissances requises avant de suivre ce cours",
        verbose_name="Prérequis"
    )
    learning_objectives = models.TextField(
        blank=True,
        help_text="Ce que l'étudiant apprendra dans ce cours",
        verbose_name="Objectifs d'apprentissage"
    )
    target_audience = models.TextField(
        blank=True,
        help_text="À qui s'adresse ce cours",
        verbose_name="Public cible"
    )
    
    # Statut et publication
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name="Statut"
    )
    is_featured = models.BooleanField(default=False, verbose_name="Cours mis en avant")
    publish_date = models.DateTimeField(blank=True, null=True, verbose_name="Date de publication")
    
    # Certificat
    has_certificate = models.BooleanField(default=False, verbose_name="Délivre un certificat")
    certificate_template = models.FileField(
        upload_to='courses/certificates/',
        blank=True,
        null=True,
        verbose_name="Modèle de certificat"
    )
    
    # SEO et métadonnées
    meta_description = models.CharField(
        max_length=160,
        blank=True,
        help_text="Description pour les moteurs de recherche",
        verbose_name="Meta description"
    )
    meta_keywords = models.CharField(
        max_length=255,
        blank=True,
        help_text="Mots-clés séparés par des virgules",
        verbose_name="Meta mots-clés"
    )
    
    # Statistiques
    view_count = models.PositiveIntegerField(default=0, verbose_name="Nombre de vues")
    enrollment_count = models.PositiveIntegerField(default=0, verbose_name="Nombre d'inscriptions")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Cours"
        verbose_name_plural = "Cours"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'is_featured']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['instructor', 'status']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('courses:detail', kwargs={'slug': self.slug})
    
    @property
    def total_modules(self):
        return self.modules.count()
    
    @property
    def total_lessons(self):
        return sum(module.lessons.count() for module in self.modules.all())
    
    @property
    def total_duration(self):
        """Calcule la durée totale basée sur les leçons"""
        total = 0
        for module in self.modules.all():
            for lesson in module.lessons.all():
                if lesson.duration:
                    total += lesson.duration.total_seconds()
        return total / 3600 if total > 0 else 0  # Retourne en heures
    
    @property
    def completion_rate(self):
        """Taux de complétion moyen des étudiants inscrits"""
        # À implémenter avec les modèles d'enrollment
        return 0
    
    @property
    def average_rating(self):
        """Note moyenne du cours"""
        # À implémenter avec les modèles de reviews
        return 0
    
    @property
    def is_full(self):
        """Vérifie si le cours a atteint sa capacité maximale"""
        if not self.max_students:
            return False
        return self.enrollment_count >= self.max_students
    
    def can_be_enrolled_by(self, user):
        """Vérifie si un utilisateur peut s'inscrire à ce cours"""
        if self.status != 'published':
            return False, "Ce cours n'est pas encore publié"
        
        if self.is_full:
            return False, "Ce cours a atteint sa capacité maximale"
        
        # Vérifier si déjà inscrit (à implémenter avec Enrollment)
        # if user.enrollments.filter(course=self).exists():
        #     return False, "Vous êtes déjà inscrit à ce cours"
        
        return True, "Inscription possible"


class Tag(models.Model):
    """Mots-clés pour les cours"""
    name = models.CharField(max_length=50, unique=True, verbose_name="Nom")
    slug = models.SlugField(max_length=60, unique=True, blank=True)
    color = models.CharField(
        max_length=7,
        default="#6c757d",
        help_text="Couleur hexadécimale",
        verbose_name="Couleur"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Mot-clé"
        verbose_name_plural = "Mots-clés"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Module(models.Model):
    """Modules d'un cours - niveau intermédiaire de la hiérarchie"""
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='modules',
        verbose_name="Cours"
    )
    title = models.CharField(max_length=200, verbose_name="Titre")
    description = models.TextField(blank=True, verbose_name="Description")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre")
    
    # Configuration du module
    is_free = models.BooleanField(
        default=False,
        help_text="Si coché, ce module sera accessible gratuitement",
        verbose_name="Module gratuit"
    )
    estimated_duration = models.DurationField(
        blank=True,
        null=True,
        verbose_name="Durée estimée"
    )
    
    # Prérequis pour ce module
    prerequisites = models.TextField(
        blank=True,
        help_text="Prérequis spécifiques à ce module",
        verbose_name="Prérequis"
    )
    learning_objectives = models.TextField(
        blank=True,
        help_text="Objectifs spécifiques de ce module",
        verbose_name="Objectifs"
    )
    
    # Publication
    is_published = models.BooleanField(default=False, verbose_name="Publié")
    publish_date = models.DateTimeField(blank=True, null=True, verbose_name="Date de publication")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Module"
        verbose_name_plural = "Modules"
        ordering = ['course', 'order', 'title']
        unique_together = ['course', 'order']
    
    def __str__(self):
        return f"{self.course.title} - Module {self.order}: {self.title}"
    
    @property
    def total_lessons(self):
        return self.lessons.count()
    
    @property
    def total_duration(self):
        """Durée totale calculée à partir des leçons"""
        total = 0
        for lesson in self.lessons.all():
            if lesson.duration:
                total += lesson.duration.total_seconds()
        return total / 3600 if total > 0 else 0  # En heures
    
    @property
    def completion_rate(self):
        """Taux de complétion moyen pour ce module"""
        # À implémenter avec les progrès utilisateur
        return 0


class Lesson(models.Model):
    """Leçons individuelles dans un module"""
    LESSON_TYPES = [
        ('video', 'Vidéo'),
        ('text', 'Texte'),
        ('audio', 'Audio'),
        ('document', 'Document'),
        ('quiz', 'Quiz'),
        ('assignment', 'Devoir'),
        ('live', 'Session en direct'),
        ('external', 'Lien externe'),
    ]
    
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='lessons',
        verbose_name="Module"
    )
    title = models.CharField(max_length=200, verbose_name="Titre")
    description = models.TextField(blank=True, verbose_name="Description")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre")
    
    # Type et contenu
    lesson_type = models.CharField(
        max_length=20,
        choices=LESSON_TYPES,
        default='text',
        verbose_name="Type de leçon"
    )
    content = models.TextField(blank=True, verbose_name="Contenu textuel")
    
    # Médias et fichiers
    video_url = models.URLField(
        blank=True,
        help_text="URL YouTube, Vimeo ou autre",
        verbose_name="URL vidéo"
    )
    video_file = models.FileField(
        upload_to='courses/videos/',
        blank=True,
        null=True,
        verbose_name="Fichier vidéo"
    )
    audio_file = models.FileField(
        upload_to='courses/audio/',
        blank=True,
        null=True,
        verbose_name="Fichier audio"
    )
    document_file = models.FileField(
        upload_to='courses/documents/',
        blank=True,
        null=True,
        verbose_name="Document"
    )
    external_url = models.URLField(
        blank=True,
        help_text="Lien vers une ressource externe",
        verbose_name="URL externe"
    )
    
    # Paramètres temporels
    duration = models.DurationField(
        blank=True,
        null=True,
        help_text="Durée de la leçon",
        verbose_name="Durée"
    )
    
    # Configuration
    is_preview = models.BooleanField(
        default=False,
        help_text="Si coché, accessible avant inscription",
        verbose_name="Aperçu gratuit"
    )
    is_mandatory = models.BooleanField(
        default=True,
        help_text="Cette leçon est-elle obligatoire pour la progression ?",
        verbose_name="Obligatoire"
    )
    
    # Publication
    is_published = models.BooleanField(default=False, verbose_name="Publiée")
    
    # Métadonnées
    notes = models.TextField(
        blank=True,
        help_text="Notes pour l'instructeur",
        verbose_name="Notes privées"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Leçon"
        verbose_name_plural = "Leçons"
        ordering = ['module', 'order', 'title']
        unique_together = ['module', 'order']
    
    def __str__(self):
        return f"{self.module.title} - Leçon {self.order}: {self.title}"
    
    def get_content_url(self):
        """Retourne l'URL du contenu principal selon le type"""
        if self.lesson_type == 'video':
            return self.video_url or (self.video_file.url if self.video_file else None)
        elif self.lesson_type == 'audio':
            return self.audio_file.url if self.audio_file else None
        elif self.lesson_type == 'document':
            return self.document_file.url if self.document_file else None
        elif self.lesson_type == 'external':
            return self.external_url
        return None
    
    def has_content(self):
        """Vérifie si la leçon a du contenu"""
        if self.content.strip():
            return True
        return bool(self.get_content_url())
    
    @property
    def duration_in_minutes(self):
        """Durée en minutes"""
        if self.duration:
            return self.duration.total_seconds() / 60
        return 0


class LessonResource(models.Model):
    """Ressources additionnelles pour une leçon"""
    RESOURCE_TYPES = [
        ('pdf', 'PDF'),
        ('doc', 'Document Word'),
        ('ppt', 'Présentation'),
        ('zip', 'Archive'),
        ('link', 'Lien'),
        ('image', 'Image'),
        ('other', 'Autre'),
    ]
    
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='resources',
        verbose_name="Leçon"
    )
    title = models.CharField(max_length=200, verbose_name="Titre")
    description = models.TextField(blank=True, verbose_name="Description")
    resource_type = models.CharField(
        max_length=20,
        choices=RESOURCE_TYPES,
        verbose_name="Type de ressource"
    )
    
    # Fichier ou URL
    file = models.FileField(
        upload_to='courses/resources/',
        blank=True,
        null=True,
        verbose_name="Fichier"
    )
    url = models.URLField(blank=True, verbose_name="URL")
    
    # Configuration
    is_downloadable = models.BooleanField(default=True, verbose_name="Téléchargeable")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Ressource"
        verbose_name_plural = "Ressources"
        ordering = ['lesson', 'order', 'title']
    
    def __str__(self):
        return f"{self.lesson.title} - {self.title}"
    
    def get_resource_url(self):
        """Retourne l'URL de la ressource"""
        return self.url or (self.file.url if self.file else None)


class Enrollment(models.Model):
    """Inscriptions des utilisateurs aux cours"""
    STATUS_CHOICES = [
        ('active', 'Actif'),
        ('completed', 'Terminé'),
        ('dropped', 'Abandonné'),
        ('expired', 'Expiré'),
    ]
    
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name="Utilisateur"
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name="Cours"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name="Statut"
    )
    
    # Dates importantes
    enrolled_at = models.DateTimeField(auto_now_add=True, verbose_name="Date d'inscription")
    started_at = models.DateTimeField(blank=True, null=True, verbose_name="Date de début")
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name="Date de completion")
    last_accessed = models.DateTimeField(blank=True, null=True, verbose_name="Dernier accès")
    
    # Progression
    progress_percentage = models.FloatField(default=0.0, verbose_name="Pourcentage de progression")
    current_lesson = models.ForeignKey(
        Lesson,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name="Leçon actuelle"
    )
    
    # Paiement (pour les cours payants)
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name="Montant payé"
    )
    payment_date = models.DateTimeField(blank=True, null=True, verbose_name="Date de paiement")
    transaction_id = models.CharField(max_length=100, blank=True, verbose_name="ID transaction")
    
    class Meta:
        verbose_name = "Inscription"
        verbose_name_plural = "Inscriptions"
        unique_together = ['user', 'course']
        ordering = ['-enrolled_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['course', 'status']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.course.title}"
    
    def update_progress(self):
        """Met à jour le pourcentage de progression"""
        if not self.course.modules.exists():
            return
        
        total_lessons = Lesson.objects.filter(
            module__course=self.course,
            is_published=True
        ).count()
        
        if total_lessons == 0:
            self.progress_percentage = 0.0
        else:
            completed_lessons = self.completed_lessons.count()
            self.progress_percentage = (completed_lessons / total_lessons) * 100
        
        self.save()


class LessonCompletion(models.Model):
    """Suivi de completion des leçons"""
    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name='completed_lessons',
        verbose_name="Inscription"
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        verbose_name="Leçon"
    )
    completed_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de completion")
    time_spent = models.DurationField(blank=True, null=True, verbose_name="Temps passé")
    
    class Meta:
        verbose_name = "Completion de leçon"
        verbose_name_plural = "Completions de leçons"
        unique_together = ['enrollment', 'lesson']
        ordering = ['-completed_at']
    
    def __str__(self):
        return f"{self.enrollment.user.username} - {self.lesson.title}"


class CourseFavorite(models.Model):
    """Cours favoris des utilisateurs"""
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='favorite_courses',
        verbose_name="Utilisateur"
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='favorited_by',
        verbose_name="Cours"
    )
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="Ajouté le")
    
    class Meta:
        verbose_name = "Cours favori"
        verbose_name_plural = "Cours favoris"
        unique_together = ['user', 'course']
        ordering = ['-added_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.course.title}"


class CourseReview(models.Model):
    """Avis et notes sur les cours"""
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='course_reviews',
        verbose_name="Utilisateur"
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name="Cours"
    )
    rating = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        verbose_name="Note"
    )
    title = models.CharField(max_length=200, blank=True, verbose_name="Titre")
    comment = models.TextField(blank=True, verbose_name="Commentaire")
    is_approved = models.BooleanField(default=True, verbose_name="Approuvé")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")
    
    class Meta:
        verbose_name = "Avis"
        verbose_name_plural = "Avis"
        unique_together = ['user', 'course']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.course.title} ({self.rating}★)"