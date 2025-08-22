from django.contrib import admin
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from django.utils import timezone
from django.contrib.admin.decorators import register
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.contrib import messages

from .models import CertificateTemplate, Certificate, CertificateShare
from .services import certificate_generator


@admin.register(CertificateTemplate)
class CertificateTemplateAdmin(admin.ModelAdmin):
    """Administration des templates de certificats"""
    
    list_display = [
        'name', 'template_type', 'is_default', 'is_active', 
        'created_at', 'preview_colors'
    ]
    list_filter = ['template_type', 'is_default', 'is_active', 'created_at']
    search_fields = ['name', 'title_text']
    readonly_fields = ['id', 'created_at', 'updated_at', 'preview_template']
    
    fieldsets = [
        ('Informations générales', {
            'fields': ['name', 'template_type', 'is_default', 'is_active', 'created_by']
        }),
        ('Configuration visuelle', {
            'fields': [
                'background_image', 'background_color', 'border_color', 'border_width',
                'logo', 'signature_image'
            ],
            'classes': ['collapse']
        }),
        ('Textes personnalisables', {
            'fields': [
                'title_text', 'subtitle_text', 'completion_text', 'signature_text'
            ]
        }),
        ('Configuration typographique', {
            'fields': [
                'title_font_size', 'name_font_size', 'course_font_size',
                'title_color', 'name_color', 'course_color'
            ],
            'classes': ['collapse']
        }),
        ('Aperçu', {
            'fields': ['preview_template'],
            'classes': ['collapse']
        }),
        ('Métadonnées', {
            'fields': ['id', 'created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def preview_colors(self, obj):
        """Aperçu des couleurs du template"""
        html = f"""
        <div style="display: flex; gap: 5px;">
            <div style="width: 20px; height: 20px; background: {obj.background_color}; border: 1px solid #ddd;" title="Fond"></div>
            <div style="width: 20px; height: 20px; background: {obj.border_color}; border: 1px solid #ddd;" title="Bordure"></div>
            <div style="width: 20px; height: 20px; background: {obj.title_color}; border: 1px solid #ddd;" title="Titre"></div>
            <div style="width: 20px; height: 20px; background: {obj.name_color}; border: 1px solid #ddd;" title="Nom"></div>
            <div style="width: 20px; height: 20px; background: {obj.course_color}; border: 1px solid #ddd;" title="Cours"></div>
        </div>
        """
        return mark_safe(html)
    preview_colors.short_description = "Couleurs"
    
    def preview_template(self, obj):
        """Aperçu du template"""
        if obj.background_image:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 200px;" />',
                obj.background_image.url
            )
        return "Pas d'image de fond"
    preview_template.short_description = "Aperçu"
    
    def save_model(self, request, obj, form, change):
        """Définit l'utilisateur créateur"""
        if not change:  # Création
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    """Administration des certificats"""
    
    list_display = [
        'certificate_number', 'recipient_name', 'course_title', 
        'status', 'final_grade', 'completion_date', 'status_badges'
    ]
    list_filter = [
        'status', 'template__template_type', 'is_public', 
        'completion_date', 'created_at'
    ]
    search_fields = [
        'certificate_number', 'recipient_name', 'course_title',
        'user__username', 'user__email'
    ]
    readonly_fields = [
        'id', 'certificate_number', 'verification_hash',
        'created_at', 'updated_at', 'generated_at', 'issued_at', 'revoked_at',
        'certificate_preview', 'verification_link'
    ]
    raw_id_fields = ['user', 'course', 'enrollment', 'template']
    
    fieldsets = [
        ('Informations principales', {
            'fields': [
                'certificate_number', 'user', 'course', 'enrollment', 'template'
            ]
        }),
        ('Données du certificat', {
            'fields': [
                'recipient_name', 'course_title', 'completion_date', 'issue_date'
            ]
        }),
        ('Performance', {
            'fields': [
                'final_grade', 'completion_percentage', 'duration_hours'
            ],
            'classes': ['collapse']
        }),
        ('Fichiers générés', {
            'fields': [
                'certificate_file', 'pdf_file', 'qr_code', 'certificate_preview'
            ]
        }),
        ('Sécurité et vérification', {
            'fields': [
                'verification_hash', 'verification_link', 'status', 'is_public'
            ]
        }),
        ('Métadonnées', {
            'fields': [
                'metadata', 'id', 'created_at', 'updated_at', 
                'generated_at', 'issued_at', 'revoked_at', 'revoked_reason'
            ],
            'classes': ['collapse']
        })
    ]
    
    actions = ['regenerate_certificates', 'issue_certificates', 'revoke_certificates']
    
    def certificate_preview(self, obj):
        """Aperçu du certificat généré"""
        if obj.certificate_file:
            return format_html(
                '<img src="{}" style="max-width: 400px; max-height: 300px;" />',
                obj.certificate_file.url
            )
        return "Certificat non généré"
    certificate_preview.short_description = "Aperçu"
    
    def verification_link(self, obj):
        """Lien de vérification du certificat"""
        if obj.verification_hash:
            url = reverse('certificates:verify', kwargs={'hash': obj.verification_hash})
            return format_html('<a href="{}" target="_blank">Vérifier</a>', url)
        return "Pas de hash de vérification"
    verification_link.short_description = "Vérification"
    
    def status_badges(self, obj):
        """Badges de statut du certificat"""
        badges = []
        
        if obj.status == 'pending':
            badges.append('<span style="color: orange;">⏳ En attente</span>')
        elif obj.status == 'generated':
            badges.append('<span style="color: blue;">✓ Généré</span>')
        elif obj.status == 'issued':
            badges.append('<span style="color: green;">✅ Délivré</span>')
        elif obj.status == 'revoked':
            badges.append('<span style="color: red;">❌ Révoqué</span>')
        
        if obj.is_public:
            badges.append('<span style="color: purple;">🌐 Public</span>')
        
        return mark_safe(' | '.join(badges))
    status_badges.short_description = "Statut"
    
    def regenerate_certificates(self, request, queryset):
        """Action pour régénérer des certificats"""
        count = 0
        for certificate in queryset:
            try:
                if certificate.enrollment:
                    # Révoquer l'ancien certificat
                    certificate.revoke("Régénéré par l'administrateur")
                    
                    # Créer un nouveau certificat
                    new_certificate = certificate_generator.generate_certificate_for_enrollment(
                        certificate.enrollment
                    )
                    
                    if new_certificate:
                        count += 1
                        
            except Exception as e:
                messages.error(request, f"Erreur lors de la régénération du certificat {certificate.certificate_number}: {e}")
        
        messages.success(request, f"{count} certificat(s) régénéré(s) avec succès.")
    regenerate_certificates.short_description = "Régénérer les certificats sélectionnés"
    
    def issue_certificates(self, request, queryset):
        """Action pour délivrer des certificats"""
        count = queryset.filter(status='generated').update(
            status='issued',
            issued_at=timezone.now()
        )
        messages.success(request, f"{count} certificat(s) délivré(s).")
    issue_certificates.short_description = "Délivrer les certificats sélectionnés"
    
    def revoke_certificates(self, request, queryset):
        """Action pour révoquer des certificats"""
        count = 0
        for certificate in queryset.exclude(status='revoked'):
            certificate.revoke("Révoqué par l'administrateur")
            count += 1
        messages.success(request, f"{count} certificat(s) révoqué(s).")
    revoke_certificates.short_description = "Révoquer les certificats sélectionnés"
    
    def get_queryset(self, request):
        """Optimise les requêtes"""
        return super().get_queryset(request).select_related(
            'user', 'course', 'template', 'enrollment'
        )


@admin.register(CertificateShare)
class CertificateShareAdmin(admin.ModelAdmin):
    """Administration des partages de certificats"""
    
    list_display = [
        'certificate', 'share_token', 'is_active', 'expires_at', 
        'view_count', 'created_at', 'share_link'
    ]
    list_filter = ['is_active', 'expires_at', 'created_at']
    search_fields = ['certificate__certificate_number', 'certificate__recipient_name']
    readonly_fields = ['share_token', 'view_count', 'created_at', 'updated_at', 'share_link']
    
    def share_link(self, obj):
        """Lien de partage"""
        url = reverse('certificates:shared_view', kwargs={'token': obj.share_token})
        return format_html('<a href="{}" target="_blank">Lien de partage</a>', url)
    share_link.short_description = "Lien"
