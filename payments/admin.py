from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Sum
from .models import PaymentTransaction, WebhookEvent, PaymentRefund, PaymentConfiguration
import json


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'reference', 'user', 'amount_display', 'status_display', 
        'payment_method', 'created_at', 'paid_at'
    ]
    list_filter = [
        'status', 'payment_method', 'currency', 'created_at', 'paid_at'
    ]
    search_fields = [
        'reference', 'notchpay_transaction_id', 'user__username', 
        'user__email', 'customer_email', 'description'
    ]
    readonly_fields = [
        'id', 'notchpay_transaction_id', 'created_at', 'updated_at',
        'notchpay_response_display', 'metadata_display'
    ]
    fieldsets = (
        ('Informations de base', {
            'fields': ('id', 'reference', 'notchpay_transaction_id', 'user')
        }),
        ('Détails du paiement', {
            'fields': ('amount', 'currency', 'description', 'status', 'payment_method')
        }),
        ('Informations client', {
            'fields': ('customer_name', 'customer_email', 'customer_phone')
        }),
        ('URLs et redirections', {
            'fields': ('authorization_url', 'return_url', 'cancel_url'),
            'classes': ('collapse',)
        }),
        ('Contenu payé', {
            'fields': ('content_type', 'object_id'),
            'classes': ('collapse',)
        }),
        ('Données financières', {
            'fields': ('processing_fee', 'net_amount'),
            'classes': ('collapse',)
        }),
        ('Gestion des erreurs', {
            'fields': ('error_code', 'error_message'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('metadata_display', 'notchpay_response_display'),
            'classes': ('collapse',)
        }),
        ('Horodatage', {
            'fields': ('created_at', 'updated_at', 'paid_at', 'expires_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'mark_as_completed', 'mark_as_failed', 'verify_status_with_notchpay'
    ]
    
    def amount_display(self, obj):
        """Affichage formaté du montant"""
        return f"{obj.amount:,.2f} {obj.currency}"
    amount_display.short_description = "Montant"
    
    def status_display(self, obj):
        """Affichage coloré du statut"""
        colors = {
            'pending': '#ffc107',
            'processing': '#17a2b8',
            'completed': '#28a745',
            'failed': '#dc3545',
            'cancelled': '#6c757d',
            'expired': '#fd7e14',
            'refunded': '#6f42c1'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = "Statut"
    
    def notchpay_response_display(self, obj):
        """Affichage formaté de la réponse Notchpay"""
        if obj.notchpay_response:
            return format_html(
                '<pre style="max-height: 200px; overflow-y: auto;">{}</pre>',
                json.dumps(obj.notchpay_response, indent=2, ensure_ascii=False)
            )
        return "Aucune réponse"
    notchpay_response_display.short_description = "Réponse Notchpay"
    
    def metadata_display(self, obj):
        """Affichage formaté des métadonnées"""
        if obj.metadata:
            return format_html(
                '<pre style="max-height: 200px; overflow-y: auto;">{}</pre>',
                json.dumps(obj.metadata, indent=2, ensure_ascii=False)
            )
        return "Aucune métadonnée"
    metadata_display.short_description = "Métadonnées"
    
    def mark_as_completed(self, request, queryset):
        """Action pour marquer les transactions comme terminées"""
        updated = queryset.filter(status__in=['pending', 'processing']).update(status='completed')
        self.message_user(request, f"{updated} transaction(s) marquée(s) comme terminée(s).")
    mark_as_completed.short_description = "Marquer comme terminé"
    
    def mark_as_failed(self, request, queryset):
        """Action pour marquer les transactions comme échouées"""
        updated = queryset.filter(status__in=['pending', 'processing']).update(status='failed')
        self.message_user(request, f"{updated} transaction(s) marquée(s) comme échouée(s).")
    mark_as_failed.short_description = "Marquer comme échoué"
    
    def verify_status_with_notchpay(self, request, queryset):
        """Action pour vérifier le statut avec Notchpay"""
        # Cette action sera implémentée avec le service Notchpay
        count = queryset.count()
        self.message_user(request, f"Vérification du statut de {count} transaction(s) programmée.")
    verify_status_with_notchpay.short_description = "Vérifier statut avec Notchpay"


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = [
        'event_id', 'event_type', 'transaction_link', 'processed_display', 'created_at'
    ]
    list_filter = ['event_type', 'processed', 'created_at']
    search_fields = ['event_id', 'transaction__reference', 'transaction__notchpay_transaction_id']
    readonly_fields = [
        'id', 'event_id', 'created_at', 'data_display', 'signature'
    ]
    fieldsets = (
        ('Informations de base', {
            'fields': ('id', 'event_id', 'event_type', 'transaction')
        }),
        ('Traitement', {
            'fields': ('processed', 'processed_at', 'error_message')
        }),
        ('Données techniques', {
            'fields': ('signature', 'data_display'),
            'classes': ('collapse',)
        }),
        ('Horodatage', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_processed', 'reprocess_events']
    
    def transaction_link(self, obj):
        """Lien vers la transaction associée"""
        if obj.transaction:
            url = reverse('admin:payments_paymenttransaction_change', args=[obj.transaction.id])
            return format_html('<a href="{}">{}</a>', url, obj.transaction.reference)
        return "Aucune transaction"
    transaction_link.short_description = "Transaction"
    
    def processed_display(self, obj):
        """Affichage coloré du statut de traitement"""
        if obj.processed:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✓ Traité</span>'
            )
        else:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">✗ En attente</span>'
            )
    processed_display.short_description = "Traité"
    
    def data_display(self, obj):
        """Affichage formaté des données"""
        if obj.data:
            return format_html(
                '<pre style="max-height: 300px; overflow-y: auto;">{}</pre>',
                json.dumps(obj.data, indent=2, ensure_ascii=False)
            )
        return "Aucune donnée"
    data_display.short_description = "Données webhook"
    
    def mark_as_processed(self, request, queryset):
        """Action pour marquer les événements comme traités"""
        updated = queryset.filter(processed=False).update(processed=True)
        self.message_user(request, f"{updated} événement(s) marqué(s) comme traité(s).")
    mark_as_processed.short_description = "Marquer comme traité"
    
    def reprocess_events(self, request, queryset):
        """Action pour retraiter les événements"""
        # Cette action sera implémentée avec le service webhook
        count = queryset.count()
        self.message_user(request, f"Retraitement de {count} événement(s) programmé.")
    reprocess_events.short_description = "Retraiter les événements"


@admin.register(PaymentRefund)
class PaymentRefundAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_link', 'amount_display', 'status_display', 'reason_short', 'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = [
        'transaction__reference', 'transaction__notchpay_transaction_id', 
        'notchpay_refund_id', 'reason'
    ]
    readonly_fields = [
        'id', 'notchpay_refund_id', 'created_at', 'processed_at',
        'notchpay_response_display'
    ]
    fieldsets = (
        ('Informations de base', {
            'fields': ('id', 'transaction', 'notchpay_refund_id')
        }),
        ('Détails du remboursement', {
            'fields': ('amount', 'reason', 'status')
        }),
        ('Métadonnées', {
            'fields': ('notchpay_response_display',),
            'classes': ('collapse',)
        }),
        ('Horodatage', {
            'fields': ('created_at', 'processed_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_completed', 'mark_as_failed']
    
    def transaction_link(self, obj):
        """Lien vers la transaction associée"""
        url = reverse('admin:payments_paymenttransaction_change', args=[obj.transaction.id])
        return format_html('<a href="{}">{}</a>', url, obj.transaction.reference)
    transaction_link.short_description = "Transaction"
    
    def amount_display(self, obj):
        """Affichage formaté du montant"""
        return f"{obj.amount:,.2f} {obj.transaction.currency}"
    amount_display.short_description = "Montant"
    
    def status_display(self, obj):
        """Affichage coloré du statut"""
        colors = {
            'pending': '#ffc107',
            'processing': '#17a2b8',
            'completed': '#28a745',
            'failed': '#dc3545'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = "Statut"
    
    def reason_short(self, obj):
        """Version courte de la raison"""
        if len(obj.reason) > 50:
            return f"{obj.reason[:47]}..."
        return obj.reason
    reason_short.short_description = "Raison"
    
    def notchpay_response_display(self, obj):
        """Affichage formaté de la réponse Notchpay"""
        if obj.notchpay_response:
            return format_html(
                '<pre style="max-height: 200px; overflow-y: auto;">{}</pre>',
                json.dumps(obj.notchpay_response, indent=2, ensure_ascii=False)
            )
        return "Aucune réponse"
    notchpay_response_display.short_description = "Réponse Notchpay"
    
    def mark_as_completed(self, request, queryset):
        """Action pour marquer les remboursements comme terminés"""
        updated = queryset.filter(status__in=['pending', 'processing']).update(status='completed')
        self.message_user(request, f"{updated} remboursement(s) marqué(s) comme terminé(s).")
    mark_as_completed.short_description = "Marquer comme terminé"
    
    def mark_as_failed(self, request, queryset):
        """Action pour marquer les remboursements comme échoués"""
        updated = queryset.filter(status__in=['pending', 'processing']).update(status='failed')
        self.message_user(request, f"{updated} remboursement(s) marqué(s) comme échoué(s).")
    mark_as_failed.short_description = "Marquer comme échoué"


@admin.register(PaymentConfiguration)
class PaymentConfigurationAdmin(admin.ModelAdmin):
    list_display = [
        'environment_display', 'is_active_display', 'default_currency', 
        'timeout_seconds', 'max_retries', 'updated_at'
    ]
    list_filter = ['environment', 'is_active', 'default_currency']
    fieldsets = (
        ('Configuration générale', {
            'fields': ('environment', 'is_active', 'default_currency')
        }),
        ('Clés API', {
            'fields': ('public_key', 'private_key'),
            'description': 'Les clés API Notchpay pour cet environnement'
        }),
        ('Configuration webhook', {
            'fields': ('webhook_url', 'webhook_secret'),
            'classes': ('collapse',)
        }),
        ('URLs par défaut', {
            'fields': ('default_return_url', 'default_cancel_url'),
            'classes': ('collapse',)
        }),
        ('Paramètres techniques', {
            'fields': ('timeout_seconds', 'max_retries'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_configuration', 'test_api_connection']
    
    def environment_display(self, obj):
        """Affichage coloré de l'environnement"""
        if obj.environment == 'production':
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">🔴 Production</span>'
            )
        else:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">🟢 Sandbox</span>'
            )
    environment_display.short_description = "Environnement"
    
    def is_active_display(self, obj):
        """Affichage coloré du statut actif"""
        if obj.is_active:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✓ Actif</span>'
            )
        else:
            return format_html(
                '<span style="color: #6c757d; font-weight: bold;">✗ Inactif</span>'
            )
    is_active_display.short_description = "Statut"
    
    def activate_configuration(self, request, queryset):
        """Action pour activer une configuration"""
        # Désactiver toutes les autres configurations
        PaymentConfiguration.objects.update(is_active=False)
        # Activer la configuration sélectionnée
        if queryset.count() == 1:
            queryset.update(is_active=True)
            config = queryset.first()
            self.message_user(
                request, 
                f"Configuration {config.get_environment_display()} activée."
            )
        else:
            self.message_user(
                request, 
                "Veuillez sélectionner une seule configuration à activer.",
                level='ERROR'
            )
    activate_configuration.short_description = "Activer cette configuration"
    
    def test_api_connection(self, request, queryset):
        """Action pour tester la connexion API"""
        # Cette action sera implémentée avec le service Notchpay
        count = queryset.count()
        self.message_user(request, f"Test de connexion API pour {count} configuration(s) programmé.")
    test_api_connection.short_description = "Tester la connexion API"
    
    def save_model(self, request, obj, form, change):
        """Override pour s'assurer qu'une seule configuration est active"""
        if obj.is_active:
            # Désactiver toutes les autres configurations
            PaymentConfiguration.objects.exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)


# Configuration personnalisée de l'admin
admin.site.site_header = "eSchool - Administration des Paiements"
admin.site.site_title = "eSchool Payments"
admin.site.index_title = "Gestion des Paiements Notchpay"
