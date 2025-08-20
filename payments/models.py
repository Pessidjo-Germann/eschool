import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from decimal import Decimal
import json

User = get_user_model()


class Invoice(models.Model):
    """Modèle pour les factures générées automatiquement"""
    
    INVOICE_STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('sent', 'Envoyée'),
        ('paid', 'Payée'),
        ('cancelled', 'Annulée'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(
        max_length=50, 
        unique=True,
        help_text="Numéro de facture généré automatiquement"
    )
    
    # Relations
    transaction = models.OneToOneField(
        'PaymentTransaction',
        on_delete=models.CASCADE,
        related_name='invoice',
        help_text="Transaction associée à cette facture"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='invoices'
    )
    
    # Informations de facturation
    billing_name = models.CharField(max_length=200)
    billing_email = models.EmailField()
    billing_phone = models.CharField(max_length=20, blank=True)
    billing_address = models.TextField(blank=True)
    billing_city = models.CharField(max_length=100, blank=True)
    billing_country = models.CharField(max_length=100, default='Cameroun')
    
    # Détails financiers
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='XAF')
    
    # Statut et dates
    status = models.CharField(
        max_length=20,
        choices=INVOICE_STATUS_CHOICES,
        default='draft'
    )
    issue_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    
    # Fichiers générés
    pdf_file = models.FileField(
        upload_to='invoices/pdf/',
        null=True, blank=True,
        help_text="Fichier PDF de la facture"
    )
    
    # Métadonnées
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Suivi email
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    email_opened = models.BooleanField(default=False)
    email_opened_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Facture"
        verbose_name_plural = "Factures"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invoice_number']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['issue_date', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"Facture {self.invoice_number} - {self.billing_name}"
    
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self._generate_invoice_number()
        
        # Calculer automatiquement les totaux
        if self.subtotal:
            self.tax_amount = self.subtotal * self.tax_rate
            self.total_amount = self.subtotal + self.tax_amount
        
        # Définir la date d'échéance (30 jours par défaut)
        if not self.due_date:
            from datetime import date, timedelta
            self.due_date = date.today() + timedelta(days=30)
        
        super().save(*args, **kwargs)
    
    def _generate_invoice_number(self):
        """Générer un numéro de facture unique"""
        from datetime import date
        today = date.today()
        year = today.year
        month = today.month
        
        # Format: INV-YYYY-MM-XXXX
        prefix = f"INV-{year}-{month:02d}"
        
        # Compter les factures du mois
        count = Invoice.objects.filter(
            invoice_number__startswith=prefix
        ).count() + 1
        
        return f"{prefix}-{count:04d}"
    
    @property
    def is_overdue(self):
        """Vérifier si la facture est en retard"""
        from datetime import date
        return self.status != 'paid' and self.due_date < date.today()
    
    @property
    def days_until_due(self):
        """Nombre de jours avant l'échéance"""
        from datetime import date
        if self.status == 'paid':
            return 0
        delta = self.due_date - date.today()
        return delta.days
    
    def mark_as_paid(self):
        """Marquer la facture comme payée"""
        from datetime import date
        self.status = 'paid'
        self.paid_date = date.today()
        self.save()
    
    def mark_email_sent(self):
        """Marquer l'email comme envoyé"""
        from django.utils import timezone
        self.email_sent = True
        self.email_sent_at = timezone.now()
        if self.status == 'draft':
            self.status = 'sent'
        self.save()
    
    def mark_email_opened(self):
        """Marquer l'email comme ouvert"""
        from django.utils import timezone
        self.email_opened = True
        self.email_opened_at = timezone.now()
        self.save()


class PaymentTransaction(models.Model):
    """Modèle principal pour les transactions de paiement Notchpay"""
    
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En cours de traitement'),
        ('completed', 'Terminé'),
        ('failed', 'Échoué'),
        ('cancelled', 'Annulé'),
        ('expired', 'Expiré'),
        ('refunded', 'Remboursé'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('mtn_momo', 'MTN Mobile Money'),
        ('orange_money', 'Orange Money'),
        ('express_union', 'Express Union'),
        ('card', 'Carte bancaire'),
        ('bank_transfer', 'Virement bancaire'),
    ]
    
    CURRENCY_CHOICES = [
        ('XAF', 'Franc CFA (CEMAC)'),
        ('XOF', 'Franc CFA (UEMOA)'),
        ('USD', 'Dollar américain'),
        ('EUR', 'Euro'),
    ]
    
    # Identifiants
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notchpay_transaction_id = models.CharField(
        max_length=100, 
        unique=True, 
        null=True, 
        blank=True,
        help_text="ID de transaction fourni par Notchpay"
    )
    reference = models.CharField(
        max_length=100, 
        unique=True,
        help_text="Référence unique interne"
    )
    
    # Utilisateur et contenu
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='payment_transactions'
    )
    
    # Informations de paiement
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Montant en unité principale de la devise"
    )
    currency = models.CharField(
        max_length=3, 
        choices=CURRENCY_CHOICES, 
        default='XAF'
    )
    description = models.TextField(
        help_text="Description du paiement"
    )
    
    # Statut et méthode
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending'
    )
    payment_method = models.CharField(
        max_length=20, 
        choices=PAYMENT_METHOD_CHOICES, 
        null=True, 
        blank=True
    )
    
    # Informations client
    customer_name = models.CharField(max_length=100)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20, null=True, blank=True)
    
    # URLs et redirections
    authorization_url = models.URLField(
        null=True, 
        blank=True,
        help_text="URL de redirection fournie par Notchpay"
    )
    return_url = models.URLField(
        null=True, 
        blank=True,
        help_text="URL de retour après paiement"
    )
    cancel_url = models.URLField(
        null=True, 
        blank=True,
        help_text="URL de retour en cas d'annulation"
    )
    
    # Métadonnées et réponses API
    metadata = models.JSONField(
        default=dict,
        help_text="Métadonnées additionnelles"
    )
    notchpay_response = models.JSONField(
        default=dict,
        help_text="Réponse complète de l'API Notchpay"
    )
    
    # Horodatage
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Date et heure du paiement réussi"
    )
    expires_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Date d'expiration de la transaction"
    )
    
    # Informations de traitement
    processing_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Frais de traitement"
    )
    net_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Montant net après déduction des frais"
    )
    
    # Gestion des erreurs
    error_code = models.CharField(
        max_length=50, 
        null=True, 
        blank=True,
        help_text="Code d'erreur en cas d'échec"
    )
    error_message = models.TextField(
        null=True, 
        blank=True,
        help_text="Message d'erreur détaillé"
    )
    
    # Relation avec le contenu payé (générique)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Type de contenu payé (cours, quiz, etc.)"
    )
    object_id = models.CharField(max_length=100, null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    class Meta:
        verbose_name = "Transaction de paiement"
        verbose_name_plural = "Transactions de paiement"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['notchpay_transaction_id']),
            models.Index(fields=['reference']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.reference} - {self.amount} {self.currency} ({self.status})"
    
    def save(self, *args, **kwargs):
        # Générer une référence unique si pas fournie
        if not self.reference:
            self.reference = f"PAY_{timezone.now().strftime('%Y%m%d_%H%M%S')}_{str(self.id)[:8]}"
        
        # Calculer le montant net
        if self.net_amount is None and self.status == 'completed':
            self.net_amount = self.amount - self.processing_fee
        
        super().save(*args, **kwargs)
    
    @property
    def is_successful(self):
        """Vérifie si le paiement a réussi"""
        return self.status == 'completed'
    
    @property
    def is_pending(self):
        """Vérifie si le paiement est en attente"""
        return self.status in ['pending', 'processing']
    
    @property
    def is_failed(self):
        """Vérifie si le paiement a échoué"""
        return self.status in ['failed', 'cancelled', 'expired']
    
    @property
    def amount_in_cents(self):
        """Retourne le montant en centimes (plus petite unité de devise)"""
        return int(self.amount * 100)
    
    def get_metadata(self, key, default=None):
        """Récupère une métadonnée spécifique"""
        return self.metadata.get(key, default)
    
    def set_metadata(self, key, value):
        """Définit une métadonnée"""
        self.metadata[key] = value
        self.save(update_fields=['metadata'])
    
    def mark_as_completed(self, notchpay_data=None):
        """Marque la transaction comme terminée"""
        self.status = 'completed'
        self.paid_at = timezone.now()
        if notchpay_data:
            self.notchpay_response.update(notchpay_data)
        self.save()
    
    def mark_as_failed(self, error_code=None, error_message=None):
        """Marque la transaction comme échouée"""
        self.status = 'failed'
        if error_code:
            self.error_code = error_code
        if error_message:
            self.error_message = error_message
        self.save()


class WebhookEvent(models.Model):
    """Modèle pour stocker les événements webhook de Notchpay"""
    
    EVENT_TYPES = [
        ('payment.completed', 'Paiement terminé'),
        ('payment.failed', 'Paiement échoué'),
        ('payment.pending', 'Paiement en attente'),
        ('payment.cancelled', 'Paiement annulé'),
        ('refund.created', 'Remboursement créé'),
        ('refund.completed', 'Remboursement terminé'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.CharField(
        max_length=100, 
        unique=True,
        help_text="ID unique de l'événement Notchpay"
    )
    event_type = models.CharField(
        max_length=50, 
        choices=EVENT_TYPES
    )
    transaction = models.ForeignKey(
        PaymentTransaction,
        on_delete=models.CASCADE,
        related_name='webhook_events',
        null=True,
        blank=True
    )
    
    # Données de l'événement
    data = models.JSONField(
        help_text="Données complètes de l'événement webhook"
    )
    signature = models.CharField(
        max_length=500,
        help_text="Signature de vérification du webhook"
    )
    
    # Traitement
    processed = models.BooleanField(
        default=False,
        help_text="Indique si l'événement a été traité"
    )
    processed_at = models.DateTimeField(
        null=True, 
        blank=True
    )
    error_message = models.TextField(
        null=True, 
        blank=True,
        help_text="Message d'erreur si le traitement a échoué"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Événement Webhook"
        verbose_name_plural = "Événements Webhook"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.event_type} - {self.event_id}"
    
    def mark_as_processed(self):
        """Marque l'événement comme traité"""
        self.processed = True
        self.processed_at = timezone.now()
        self.save()


class PaymentRefund(models.Model):
    """Modèle pour les remboursements"""
    
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En cours'),
        ('completed', 'Terminé'),
        ('failed', 'Échoué'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(
        PaymentTransaction,
        on_delete=models.CASCADE,
        related_name='refunds'
    )
    notchpay_refund_id = models.CharField(
        max_length=100, 
        unique=True, 
        null=True, 
        blank=True
    )
    
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Montant du remboursement"
    )
    reason = models.TextField(
        help_text="Raison du remboursement"
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending'
    )
    
    # Métadonnées
    notchpay_response = models.JSONField(
        default=dict,
        help_text="Réponse de l'API Notchpay pour le remboursement"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Remboursement"
        verbose_name_plural = "Remboursements"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Remboursement {self.amount} {self.transaction.currency} - {self.transaction.reference}"


class PaymentConfiguration(models.Model):
    """Configuration des paramètres de paiement Notchpay"""
    
    ENVIRONMENT_CHOICES = [
        ('sandbox', 'Sandbox (Test)'),
        ('production', 'Production'),
    ]
    
    environment = models.CharField(
        max_length=20,
        choices=ENVIRONMENT_CHOICES,
        default='sandbox'
    )
    
    # Clés API
    public_key = models.CharField(
        max_length=200,
        help_text="Clé publique Notchpay"
    )
    private_key = models.CharField(
        max_length=200,
        help_text="Clé privée Notchpay"
    )
    
    # Configuration webhook
    webhook_url = models.URLField(
        null=True,
        blank=True,
        help_text="URL de réception des webhooks"
    )
    webhook_secret = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="Secret pour vérifier les signatures webhook"
    )
    
    # Paramètres par défaut
    default_currency = models.CharField(
        max_length=3,
        choices=PaymentTransaction.CURRENCY_CHOICES,
        default='XAF'
    )
    
    # URLs par défaut
    default_return_url = models.URLField(
        null=True,
        blank=True,
        help_text="URL de retour par défaut après paiement"
    )
    default_cancel_url = models.URLField(
        null=True,
        blank=True,
        help_text="URL de retour par défaut en cas d'annulation"
    )
    
    # Paramètres de timeout et retry
    timeout_seconds = models.PositiveIntegerField(
        default=30,
        help_text="Timeout pour les requêtes API (secondes)"
    )
    max_retries = models.PositiveIntegerField(
        default=3,
        help_text="Nombre maximum de tentatives"
    )
    
    # Activation
    is_active = models.BooleanField(
        default=True,
        help_text="Active/désactive le système de paiement"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuration de paiement"
        verbose_name_plural = "Configurations de paiement"
    
    def __str__(self):
        return f"Configuration Notchpay ({self.environment})"
    
    @classmethod
    def get_active_config(cls):
        """Récupère la configuration active"""
        return cls.objects.filter(is_active=True).first()
    
    @property
    def is_sandbox(self):
        """Vérifie si nous sommes en mode sandbox"""
        return self.environment == 'sandbox'