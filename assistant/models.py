import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import json

User = get_user_model()


class Conversation(models.Model):
    """Modèle pour gérer les conversations avec l'assistant"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='conversations',
        null=True, blank=True  # Pour permettre les conversations anonymes
    )
    session_id = models.CharField(
        max_length=100,
        help_text="ID de session pour les utilisateurs anonymes"
    )
    title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Titre généré automatiquement basé sur le premier message"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    # Métadonnées pour le contexte
    context_data = models.JSONField(
        default=dict,
        help_text="Données de contexte (cours actuel, préférences utilisateur, etc.)"
    )
    
    class Meta:
        ordering = ['-updated_at']
        verbose_name = "Conversation"
        verbose_name_plural = "Conversations"
    
    def __str__(self):
        user_info = self.user.username if self.user else f"Session {self.session_id[:8]}"
        return f"Conversation {user_info} - {self.title or 'Sans titre'}"
    
    def get_context_value(self, key, default=None):
        """Récupère une valeur du contexte"""
        return self.context_data.get(key, default)
    
    def set_context_value(self, key, value):
        """Définit une valeur dans le contexte"""
        self.context_data[key] = value
        self.save(update_fields=['context_data'])


class Message(models.Model):
    """Modèle pour les messages individuels dans une conversation"""
    
    ROLE_CHOICES = [
        ('user', 'Utilisateur'),
        ('assistant', 'Assistant'),
        ('system', 'Système'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Métadonnées pour l'assistant
    metadata = models.JSONField(
        default=dict,
        help_text="Métadonnées comme les tokens utilisés, temps de réponse, etc."
    )
    
    # Pour les fonctionnalités avancées
    is_helpful = models.BooleanField(
        null=True, blank=True,
        help_text="L'utilisateur a-t-il trouvé cette réponse utile?"
    )
    
    class Meta:
        ordering = ['timestamp']
        verbose_name = "Message"
        verbose_name_plural = "Messages"
    
    def __str__(self):
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"{self.get_role_display()}: {content_preview}"


class KnowledgeBase(models.Model):
    """Base de connaissances pour les FAQ et informations du système"""
    
    CATEGORY_CHOICES = [
        ('general', 'Général'),
        ('courses', 'Cours'),
        ('payments', 'Paiements'),
        ('account', 'Compte utilisateur'),
        ('technical', 'Support technique'),
        ('enrollment', 'Inscription'),
        ('certificates', 'Certificats'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, verbose_name="Titre")
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='general',
        verbose_name="Catégorie"
    )
    question = models.TextField(verbose_name="Question")
    answer = models.TextField(verbose_name="Réponse")
    
    # Mots-clés pour la recherche
    keywords = models.TextField(
        blank=True,
        help_text="Mots-clés séparés par des virgules pour améliorer la recherche"
    )
    
    # Gestion
    is_active = models.BooleanField(default=True, verbose_name="Active")
    priority = models.IntegerField(
        default=0,
        help_text="Priorité d'affichage (plus élevé = plus prioritaire)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='knowledge_entries'
    )
    
    # Statistiques d'utilisation
    usage_count = models.PositiveIntegerField(
        default=0,
        help_text="Nombre de fois que cette entrée a été utilisée"
    )
    last_used = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-priority', '-updated_at']
        verbose_name = "Entrée de base de connaissances"
        verbose_name_plural = "Base de connaissances"
    
    def __str__(self):
        return f"[{self.get_category_display()}] {self.title}"
    
    def increment_usage(self):
        """Incrémente le compteur d'utilisation"""
        self.usage_count += 1
        self.last_used = timezone.now()
        self.save(update_fields=['usage_count', 'last_used'])
    
    def get_keywords_list(self):
        """Retourne la liste des mots-clés"""
        return [kw.strip() for kw in self.keywords.split(',') if kw.strip()]


class AssistantConfiguration(models.Model):
    """Configuration globale de l'assistant"""
    
    MODEL_CHOICES = [
        ('gemini-2.0-flash-exp', 'Gemini 2.0 Flash (Expérimental)'),
        ('gemini-1.5-pro', 'Gemini 1.5 Pro'),
        ('gemini-1.5-flash', 'Gemini 1.5 Flash'),
    ]
    
    name = models.CharField(
        max_length=50,
        default='default',
        unique=True,
        verbose_name="Nom de la configuration"
    )
    
    # Configuration API
    api_key = models.CharField(
        max_length=200,
        help_text="Clé API Gemini"
    )
    model = models.CharField(
        max_length=50,
        choices=MODEL_CHOICES,
        default='gemini-2.0-flash-exp',
        verbose_name="Modèle Gemini"
    )
    
    # Paramètres de génération
    max_tokens = models.IntegerField(
        default=1000,
        help_text="Nombre maximum de tokens en réponse"
    )
    temperature = models.FloatField(
        default=0.7,
        help_text="Créativité des réponses (0.0 = déterministe, 1.0 = créatif)"
    )
    
    # Personnalisation
    system_prompt = models.TextField(
        default="Tu es un assistant virtuel intelligent pour une plateforme d'e-learning. "
                "Tu aides les utilisateurs avec leurs questions sur les cours, les paiements, "
                "et l'utilisation de la plateforme. Réponds toujours de manière utile, "
                "précise et amicale en français.",
        verbose_name="Prompt système"
    )
    
    # Fonctionnalités
    enable_knowledge_base = models.BooleanField(
        default=True,
        help_text="Utiliser la base de connaissances pour enrichir les réponses"
    )
    enable_context_memory = models.BooleanField(
        default=True,
        help_text="Garder en mémoire le contexte des conversations"
    )
    max_context_messages = models.IntegerField(
        default=10,
        help_text="Nombre maximum de messages précédents à inclure dans le contexte"
    )
    
    # État
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuration Assistant"
        verbose_name_plural = "Configurations Assistant"
    
    def __str__(self):
        return f"Config {self.name} - {self.get_model_display()}"
    
    @classmethod
    def get_active_config(cls):
        """Retourne la configuration active"""
        return cls.objects.filter(is_active=True).first()


class UserPreferences(models.Model):
    """Préférences utilisateur pour l'assistant"""
    
    LANGUAGE_CHOICES = [
        ('fr', 'Français'),
        ('en', 'English'),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='assistant_preferences'
    )
    
    # Préférences de communication
    preferred_language = models.CharField(
        max_length=5,
        choices=LANGUAGE_CHOICES,
        default='fr'
    )
    response_style = models.CharField(
        max_length=20,
        choices=[
            ('formal', 'Formel'),
            ('casual', 'Décontracté'),
            ('technical', 'Technique'),
        ],
        default='casual'
    )
    
    # Notifications
    enable_suggestions = models.BooleanField(
        default=True,
        help_text="Recevoir des suggestions proactives de l'assistant"
    )
    enable_course_recommendations = models.BooleanField(
        default=True,
        help_text="Recevoir des recommandations de cours"
    )
    
    # Historique
    save_conversation_history = models.BooleanField(
        default=True,
        help_text="Sauvegarder l'historique des conversations"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Préférences utilisateur"
        verbose_name_plural = "Préférences utilisateur"
    
    def __str__(self):
        return f"Préférences de {self.user.username}"
