from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone

User = get_user_model()

class SystemConfiguration(models.Model):
    """Configuration système pour la plateforme"""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Configuration système"
        verbose_name_plural = "Configurations système"

    def __str__(self):
        return f"{self.key}: {self.value[:50]}"

class ModerationLog(models.Model):
    """Log des actions de modération"""
    ACTION_CHOICES = [
        ('approve', 'Approuver'),
        ('reject', 'Rejeter'),
        ('suspend', 'Suspendre'),
        ('delete', 'Supprimer'),
        ('edit', 'Modifier'),
        ('flag', 'Signaler'),
    ]

    moderator = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    reason = models.TextField()
    
    # Generic relation pour lier à n'importe quel modèle
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Log de modération"
        verbose_name_plural = "Logs de modération"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.moderator.username} - {self.action} - {self.created_at}"

class PlatformStatistics(models.Model):
    """Statistiques quotidiennes de la plateforme"""
    date = models.DateField(unique=True)
    
    # Statistiques utilisateurs
    total_users = models.IntegerField(default=0)
    new_users = models.IntegerField(default=0)
    active_users = models.IntegerField(default=0)
    
    # Statistiques cours
    total_courses = models.IntegerField(default=0)
    new_courses = models.IntegerField(default=0)
    published_courses = models.IntegerField(default=0)
    
    # Statistiques paiements
    total_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_transactions = models.IntegerField(default=0)
    successful_transactions = models.IntegerField(default=0)
    failed_transactions = models.IntegerField(default=0)
    
    # Statistiques quiz
    total_quiz_attempts = models.IntegerField(default=0)
    avg_quiz_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Statistique plateforme"
        verbose_name_plural = "Statistiques plateforme"
        ordering = ['-date']

    def __str__(self):
        return f"Stats {self.date}"

class PaymentDispute(models.Model):
    """Gestion des litiges de paiement"""
    STATUS_CHOICES = [
        ('open', 'Ouvert'),
        ('investigating', 'En cours d\'investigation'),
        ('resolved', 'Résolu'),
        ('closed', 'Fermé'),
    ]

    DISPUTE_TYPE_CHOICES = [
        ('refund', 'Demande de remboursement'),
        ('unauthorized', 'Transaction non autorisée'),
        ('duplicate', 'Transaction dupliquée'),
        ('service_not_received', 'Service non reçu'),
        ('technical_error', 'Erreur technique'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    transaction_id = models.CharField(max_length=100)
    dispute_type = models.CharField(max_length=30, choices=DISPUTE_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    resolution_notes = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_disputes'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Litige de paiement"
        verbose_name_plural = "Litiges de paiement"
        ordering = ['-created_at']

    def __str__(self):
        return f"Litige #{self.id} - {self.user.username} - {self.amount}€"

class AdminActivity(models.Model):
    """Suivi des activités des administrateurs"""
    admin = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=100)
    description = models.TextField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Activité admin"
        verbose_name_plural = "Activités admin"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.admin.username} - {self.action} - {self.created_at}"
