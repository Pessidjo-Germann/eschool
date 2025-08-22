from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.conf import settings
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from datetime import datetime
import uuid
import hashlib
import os


class CertificateTemplate(models.Model):
    """Template pour les certificats"""
    
    TEMPLATE_TYPES = [
        ('completion', 'Completion de cours'),
        ('achievement', 'Réussite avec mention'),
        ('participation', 'Participation'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=200, 
        verbose_name="Nom du template"
    )
    template_type = models.CharField(
        max_length=20,
        choices=TEMPLATE_TYPES,
        default='completion',
        verbose_name="Type de certificat"
    )
    
    # Configuration visuelle
    background_image = models.ImageField(
        upload_to='certificates/templates/backgrounds/',
        blank=True,
        null=True,
        help_text="Image de fond (recommandé: 1920x1080px)",
        verbose_name="Image de fond"
    )
    background_color = models.CharField(
        max_length=7,
        default='#ffffff',
        help_text="Couleur de fond hexadécimale (#RRGGBB)",
        verbose_name="Couleur de fond"
    )
    border_color = models.CharField(
        max_length=7,
        default='#000000',
        help_text="Couleur de la bordure hexadécimale",
        verbose_name="Couleur bordure"
    )
    border_width = models.PositiveIntegerField(
        default=5,
        validators=[MaxValueValidator(50)],
        verbose_name="Épaisseur bordure (px)"
    )
    
    # Textes personnalisables
    title_text = models.CharField(
        max_length=200,
        default="CERTIFICAT DE COMPLETION",
        verbose_name="Titre principal"
    )
    subtitle_text = models.CharField(
        max_length=300,
        default="est décerné à",
        blank=True,
        verbose_name="Sous-titre"
    )
    completion_text = models.TextField(
        default="pour avoir complété avec succès le cours",
        verbose_name="Texte de completion"
    )
    signature_text = models.CharField(
        max_length=200,
        default="Équipe pédagogique eSchool",
        verbose_name="Texte signature"
    )
    
    # Configuration typographique
    title_font_size = models.PositiveIntegerField(
        default=48,
        validators=[MinValueValidator(12), MaxValueValidator(200)],
        verbose_name="Taille police titre"
    )
    name_font_size = models.PositiveIntegerField(
        default=36,
        validators=[MinValueValidator(12), MaxValueValidator(200)],
        verbose_name="Taille police nom"
    )
    course_font_size = models.PositiveIntegerField(
        default=28,
        validators=[MinValueValidator(12), MaxValueValidator(200)],
        verbose_name="Taille police cours"
    )
    
    # Couleurs des textes
    title_color = models.CharField(
        max_length=7,
        default='#2c3e50',
        verbose_name="Couleur titre"
    )
    name_color = models.CharField(
        max_length=7,
        default='#e74c3c',
        verbose_name="Couleur nom"
    )
    course_color = models.CharField(
        max_length=7,
        default='#34495e',
        verbose_name="Couleur cours"
    )
    
    # Logo et signature
    logo = models.ImageField(
        upload_to='certificates/templates/logos/',
        blank=True,
        null=True,
        help_text="Logo de l'organisation (recommandé: 200x200px)",
        verbose_name="Logo"
    )
    signature_image = models.ImageField(
        upload_to='certificates/templates/signatures/',
        blank=True,
        null=True,
        verbose_name="Image de signature"
    )
    
    # Configuration
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    is_default = models.BooleanField(default=False, verbose_name="Template par défaut")
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Créé par"
    )
    
    class Meta:
        verbose_name = "Template de certificat"
        verbose_name_plural = "Templates de certificats"
        ordering = ['-is_default', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"
    
    def clean(self):
        """Validation personnalisée"""
        if self.is_default:
            # S'assurer qu'il n'y a qu'un seul template par défaut par type
            existing_default = CertificateTemplate.objects.filter(
                template_type=self.template_type,
                is_default=True
            ).exclude(pk=self.pk).first()
            
            if existing_default:
                raise ValidationError(
                    f"Il existe déjà un template par défaut pour {self.get_template_type_display()}"
                )
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class Certificate(models.Model):
    """Certificats générés pour les utilisateurs"""
    
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('generated', 'Généré'),
        ('issued', 'Délivré'),
        ('revoked', 'Révoqué'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    certificate_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Numéro de certificat"
    )
    
    # Relations
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='certificates',
        verbose_name="Utilisateur"
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='certificates',
        verbose_name="Cours"
    )
    enrollment = models.OneToOneField(
        'courses.Enrollment',
        on_delete=models.CASCADE,
        related_name='certificate',
        verbose_name="Inscription"
    )
    template = models.ForeignKey(
        CertificateTemplate,
        on_delete=models.PROTECT,
        verbose_name="Template utilisé"
    )
    
    # Données du certificat
    recipient_name = models.CharField(
        max_length=200,
        verbose_name="Nom du récipiendaire"
    )
    course_title = models.CharField(
        max_length=300,
        verbose_name="Titre du cours"
    )
    completion_date = models.DateTimeField(verbose_name="Date de completion")
    issue_date = models.DateTimeField(
        default=timezone.now,
        verbose_name="Date d'émission"
    )
    
    # Données de performance (optionnelles)
    final_grade = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Note finale (%)"
    )
    completion_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Pourcentage de completion"
    )
    duration_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Durée totale (heures)"
    )
    
    # Fichier et sécurité
    certificate_file = models.ImageField(
        upload_to='certificates/generated/',
        blank=True,
        null=True,
        verbose_name="Fichier certificat"
    )
    pdf_file = models.FileField(
        upload_to='certificates/pdf/',
        blank=True,
        null=True,
        verbose_name="Certificat PDF"
    )
    verification_hash = models.CharField(
        max_length=64,
        unique=True,
        verbose_name="Hash de vérification"
    )
    qr_code = models.ImageField(
        upload_to='certificates/qr_codes/',
        blank=True,
        null=True,
        verbose_name="Code QR de vérification"
    )
    
    # Statut et configuration
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Statut"
    )
    is_public = models.BooleanField(
        default=False,
        help_text="Certificat visible publiquement",
        verbose_name="Public"
    )
    
    # Métadonnées
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Données additionnelles du certificat",
        verbose_name="Métadonnées"
    )
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.TextField(blank=True, verbose_name="Motif de révocation")
    
    class Meta:
        verbose_name = "Certificat"
        verbose_name_plural = "Certificats"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['certificate_number']),
            models.Index(fields=['verification_hash']),
            models.Index(fields=['user', 'course']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Certificat {self.certificate_number} - {self.recipient_name}"
    
    def save(self, *args, **kwargs):
        # Générer le numéro de certificat s'il n'existe pas
        if not self.certificate_number:
            self.certificate_number = self.generate_certificate_number()
        
        # Générer le hash de vérification
        if not self.verification_hash:
            self.verification_hash = self.generate_verification_hash()
        
        # Copier les données de l'inscription
        if not self.recipient_name and self.user:
            self.recipient_name = self.user.get_full_name() or self.user.username
        
        if not self.course_title and self.course:
            self.course_title = self.course.title
        
        if not self.completion_date and self.enrollment:
            self.completion_date = self.enrollment.completed_at or timezone.now()
        
        super().save(*args, **kwargs)
    
    def generate_certificate_number(self):
        """Génère un numéro unique de certificat"""
        prefix = "ESC"  # eSchool Certificate
        year = timezone.now().year
        # Utilise les 8 premiers caractères de l'UUID
        unique_part = str(uuid.uuid4()).replace('-', '').upper()[:8]
        return f"{prefix}-{year}-{unique_part}"
    
    def generate_verification_hash(self):
        """Génère un hash de vérification unique"""
        data = f"{self.user.id}{self.course.id}{self.completion_date}{timezone.now()}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def get_verification_url(self):
        """URL de vérification du certificat"""
        return reverse('certificates:verify', kwargs={'hash': self.verification_hash})
    
    def get_public_url(self):
        """URL publique du certificat si public"""
        if self.is_public:
            return reverse('certificates:public_view', kwargs={'certificate_id': self.id})
        return None
    
    def mark_as_generated(self):
        """Marque le certificat comme généré"""
        self.status = 'generated'
        self.generated_at = timezone.now()
        self.save(update_fields=['status', 'generated_at'])
    
    def mark_as_issued(self):
        """Marque le certificat comme délivré"""
        self.status = 'issued'
        self.issued_at = timezone.now()
        self.save(update_fields=['status', 'issued_at'])
    
    def revoke(self, reason=""):
        """Révoque le certificat"""
        self.status = 'revoked'
        self.revoked_at = timezone.now()
        self.revoked_reason = reason
        self.save(update_fields=['status', 'revoked_at', 'revoked_reason'])
    
    def is_valid(self):
        """Vérifie si le certificat est valide"""
        return self.status in ['generated', 'issued'] and not self.revoked_at
    
    @property
    def display_grade(self):
        """Affichage de la note avec mention"""
        if not self.final_grade:
            return "Réussi"
        
        grade = float(self.final_grade)
        if grade >= 90:
            return f"{grade}% - Excellent"
        elif grade >= 80:
            return f"{grade}% - Très bien"
        elif grade >= 70:
            return f"{grade}% - Bien"
        elif grade >= 60:
            return f"{grade}% - Assez bien"
        else:
            return f"{grade}% - Passable"


class CertificateShare(models.Model):
    """Partages publics de certificats"""
    
    certificate = models.OneToOneField(
        Certificate,
        on_delete=models.CASCADE,
        related_name='share',
        verbose_name="Certificat"
    )
    share_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        verbose_name="Token de partage"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Expire le"
    )
    view_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Nombre de vues"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Partage de certificat"
        verbose_name_plural = "Partages de certificats"
    
    def __str__(self):
        return f"Partage - {self.certificate.certificate_number}"
    
    def get_share_url(self):
        """URL de partage public"""
        return reverse('certificates:shared_view', kwargs={'token': self.share_token})
    
    def is_expired(self):
        """Vérifie si le partage a expiré"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def increment_view_count(self):
        """Incrémente le compteur de vues"""
        self.view_count += 1
        self.save(update_fields=['view_count'])
