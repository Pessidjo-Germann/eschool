from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
import uuid

User = get_user_model()

class Event(models.Model):
    """Événement générique du calendrier"""
    
    EVENT_TYPES = [
        ('course', 'Cours'),
        ('quiz', 'Quiz'),
        ('deadline', 'Échéance'),
        ('meeting', 'Réunion'),
        ('reminder', 'Rappel'),
        ('holiday', 'Congé'),
        ('maintenance', 'Maintenance'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Faible'),
        ('medium', 'Moyenne'),
        ('high', 'Élevée'),
        ('urgent', 'Urgente'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Informations de base
    title = models.CharField(max_length=200, help_text="Titre de l'événement")
    description = models.TextField(blank=True, help_text="Description détaillée")
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES, default='reminder')
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='medium')
    
    # Dates et heures
    start_date = models.DateTimeField(help_text="Date et heure de début")
    end_date = models.DateTimeField(help_text="Date et heure de fin")
    all_day = models.BooleanField(default=False, help_text="Événement toute la journée")
    
    # Relations
    organizer = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='organized_events',
        help_text="Organisateur de l'événement"
    )
    participants = models.ManyToManyField(
        User, 
        blank=True, 
        related_name='events',
        help_text="Participants à l'événement"
    )
    
    # Localisation
    location = models.CharField(max_length=200, blank=True, help_text="Lieu de l'événement")
    online_link = models.URLField(blank=True, help_text="Lien pour événement en ligne")
    
    # Récurrence
    is_recurring = models.BooleanField(default=False, help_text="Événement récurrent")
    recurrence_rule = models.TextField(
        blank=True, 
        help_text="Règle de récurrence (format RRULE RFC 5545)"
    )
    parent_event = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='recurring_instances',
        help_text="Événement parent si c'est une occurrence récurrente"
    )
    
    # Rappels
    reminder_enabled = models.BooleanField(default=True, help_text="Activer les rappels")
    reminder_minutes_before = models.PositiveIntegerField(
        default=15, 
        help_text="Minutes avant l'événement pour le rappel"
    )
    email_reminder = models.BooleanField(default=False, help_text="Rappel par email")
    
    # Couleur pour affichage
    color = models.CharField(
        max_length=7, 
        default='#3498db',
        help_text="Couleur d'affichage (format hex)"
    )
    
    # Métadonnées
    is_public = models.BooleanField(default=False, help_text="Visible publiquement")
    is_active = models.BooleanField(default=True, help_text="Événement actif")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Événement"
        verbose_name_plural = "Événements"
        ordering = ['start_date']
        indexes = [
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['organizer', 'start_date']),
            models.Index(fields=['event_type', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.start_date.strftime('%d/%m/%Y %H:%M')}"
    
    def clean(self):
        """Validation des données"""
        if self.end_date <= self.start_date:
            raise ValidationError("La date de fin doit être postérieure à la date de début")
        
        if self.all_day and (self.end_date - self.start_date).days > 7:
            raise ValidationError("Un événement toute la journée ne peut pas durer plus de 7 jours")
    
    @property
    def duration(self):
        """Durée de l'événement"""
        return self.end_date - self.start_date
    
    @property
    def duration_minutes(self):
        """Durée en minutes"""
        return int(self.duration.total_seconds() / 60)
    
    @property
    def is_past(self):
        """Vérifie si l'événement est passé"""
        return self.end_date < timezone.now()
    
    @property
    def is_current(self):
        """Vérifie si l'événement est en cours"""
        now = timezone.now()
        return self.start_date <= now <= self.end_date
    
    @property
    def is_upcoming(self):
        """Vérifie si l'événement est à venir"""
        return self.start_date > timezone.now()
    
    @property
    def time_until_start(self):
        """Temps avant le début de l'événement"""
        if self.is_past:
            return None
        return self.start_date - timezone.now()
    
    def get_participants_count(self):
        """Nombre de participants"""
        return self.participants.count()
    
    def is_participant(self, user):
        """Vérifie si un utilisateur participe à l'événement"""
        return self.participants.filter(id=user.id).exists()

class CourseSchedule(models.Model):
    """Planning spécifique pour les cours"""
    
    SCHEDULE_TYPES = [
        ('live', 'Cours en direct'),
        ('deadline', 'Échéance'),
        ('exam', 'Examen'),
        ('assignment', 'Devoir'),
    ]
    
    STATUS_CHOICES = [
        ('scheduled', 'Planifié'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminé'),
        ('cancelled', 'Annulé'),
        ('postponed', 'Reporté'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relations
    course = models.ForeignKey(
        'courses.Course', 
        on_delete=models.CASCADE, 
        related_name='schedules'
    )
    lesson = models.ForeignKey(
        'courses.Lesson', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='schedules'
    )
    
    # Informations de planning
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPES, default='live')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    
    # Dates
    scheduled_date = models.DateTimeField(help_text="Date et heure prévues")
    duration_minutes = models.PositiveIntegerField(
        default=60, 
        help_text="Durée en minutes"
    )
    
    # Informations d'accès
    access_link = models.URLField(blank=True, help_text="Lien d'accès au cours en direct")
    meeting_id = models.CharField(max_length=100, blank=True, help_text="ID de réunion")
    access_code = models.CharField(max_length=50, blank=True, help_text="Code d'accès")
    
    # Participants
    max_participants = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        help_text="Nombre maximum de participants"
    )
    enrolled_students = models.ManyToManyField(
        User, 
        through='ScheduleAttendance',
        related_name='course_schedules'
    )
    
    # Rappels automatiques
    auto_reminder = models.BooleanField(default=True)
    reminder_hours_before = models.PositiveIntegerField(
        default=24, 
        help_text="Heures avant pour l'envoi du rappel"
    )
    reminder_sent = models.BooleanField(default=False)
    
    # Métadonnées
    notes = models.TextField(blank=True, help_text="Notes pour l'instructeur")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Planning de cours"
        verbose_name_plural = "Plannings de cours"
        ordering = ['scheduled_date']
        indexes = [
            models.Index(fields=['course', 'scheduled_date']),
            models.Index(fields=['schedule_type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.course.title} - {self.get_schedule_type_display()} - {self.scheduled_date.strftime('%d/%m/%Y %H:%M')}"
    
    @property
    def end_date(self):
        """Date de fin calculée"""
        return self.scheduled_date + timedelta(minutes=self.duration_minutes)
    
    @property
    def is_past(self):
        """Vérifie si le planning est passé"""
        return self.end_date < timezone.now()
    
    @property
    def is_current(self):
        """Vérifie si le cours est en cours"""
        now = timezone.now()
        return self.scheduled_date <= now <= self.end_date
    
    @property
    def attendance_count(self):
        """Nombre de présents"""
        return self.attendances.filter(attended=True).count()
    
    def get_enrolled_count(self):
        """Nombre d'inscrits"""
        return self.enrolled_students.count()

class ScheduleAttendance(models.Model):
    """Suivi de présence aux cours planifiés"""
    
    schedule = models.ForeignKey(
        CourseSchedule, 
        on_delete=models.CASCADE, 
        related_name='attendances'
    )
    student = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='schedule_attendances'
    )
    
    # Présence
    registered = models.BooleanField(default=True, help_text="Inscrit à la session")
    attended = models.BooleanField(default=False, help_text="A participé")
    join_time = models.DateTimeField(null=True, blank=True)
    leave_time = models.DateTimeField(null=True, blank=True)
    
    # Feedback
    rating = models.PositiveSmallIntegerField(
        null=True, 
        blank=True,
        help_text="Note sur 5"
    )
    feedback = models.TextField(blank=True, help_text="Commentaire de l'étudiant")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Présence"
        verbose_name_plural = "Présences"
        unique_together = ['schedule', 'student']
    
    def __str__(self):
        return f"{self.student.username} - {self.schedule.course.title} - {'Présent' if self.attended else 'Absent'}"
    
    @property
    def duration_attended(self):
        """Durée de participation"""
        if self.join_time and self.leave_time:
            return self.leave_time - self.join_time
        return None

class EventReminder(models.Model):
    """Rappels d'événements envoyés"""
    
    REMINDER_TYPES = [
        ('email', 'Email'),
        ('push', 'Notification push'),
        ('sms', 'SMS'),
        ('in_app', 'Notification in-app'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('sent', 'Envoyé'),
        ('delivered', 'Délivré'),
        ('failed', 'Échec'),
    ]
    
    event = models.ForeignKey(
        Event, 
        on_delete=models.CASCADE, 
        related_name='reminders'
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='event_reminders'
    )
    
    reminder_type = models.CharField(max_length=10, choices=REMINDER_TYPES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    
    # Planification
    scheduled_send_time = models.DateTimeField()
    actual_send_time = models.DateTimeField(null=True, blank=True)
    
    # Contenu
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    
    # Métadonnées
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Rappel d'événement"
        verbose_name_plural = "Rappels d'événements"
        unique_together = ['event', 'user', 'reminder_type']
        ordering = ['scheduled_send_time']
    
    def __str__(self):
        return f"Rappel {self.reminder_type} - {self.event.title} - {self.user.username}"
