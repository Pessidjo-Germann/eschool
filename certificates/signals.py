from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
import logging

from courses.models import Enrollment
from .models import Certificate
from .services import certificate_generator

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Enrollment)
def generate_certificate_on_completion(sender, instance, created, **kwargs):
    """Signal pour générer automatiquement un certificat lors de la completion d'un cours"""
    
    # Vérifier si l'inscription vient d'être marquée comme complétée
    if instance.status == 'completed' and instance.completed_at:
        
        # Vérifier si un certificat existe déjà
        existing_certificate = Certificate.objects.filter(enrollment=instance).first()
        if existing_certificate:
            logger.info(f"Certificat déjà existant pour l'inscription {instance.id}")
            return
        
        try:
            logger.info(f"Génération automatique du certificat pour l'inscription {instance.id}")
            
            # Générer le certificat
            certificate = certificate_generator.generate_certificate_for_enrollment(instance)
            
            if certificate:
                logger.info(f"Certificat généré avec succès: {certificate.certificate_number}")
                
                # Envoyer une notification par email
                send_certificate_notification_email(certificate)
                
            else:
                logger.warning(f"Échec de génération du certificat pour l'inscription {instance.id}")
                
        except Exception as e:
            logger.error(f"Erreur lors de la génération automatique du certificat: {e}")


@receiver(pre_save, sender=Enrollment)
def track_enrollment_completion(sender, instance, **kwargs):
    """Suit les changements de statut pour déclencher la génération de certificats"""
    
    # Si c'est une nouvelle instance, pas de vérification
    if not instance.pk:
        return
    
    try:
        # Récupérer l'instance précédente
        previous_instance = Enrollment.objects.get(pk=instance.pk)
        
        # Vérifier si le statut vient de passer à 'completed'
        if (previous_instance.status != 'completed' and 
            instance.status == 'completed' and 
            not instance.completed_at):
            
            # Définir la date de completion automatiquement
            instance.completed_at = timezone.now()
            logger.info(f"Date de completion définie pour l'inscription {instance.id}")
            
    except Enrollment.DoesNotExist:
        # Instance nouvellement créée
        pass
    except Exception as e:
        logger.error(f"Erreur lors du suivi de l'inscription {instance.id}: {e}")


def send_certificate_notification_email(certificate):
    """Envoie un email de notification de certificat généré"""
    try:
        if not certificate.user.email:
            logger.warning(f"Pas d'email pour l'utilisateur {certificate.user.username}")
            return
        
        # Contexte pour le template email
        context = {
            'user': certificate.user,
            'certificate': certificate,
            'course': certificate.course,
            'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
        }
        
        # Rendu du template email
        subject = f"Certificat de completion - {certificate.course_title}"
        
        html_content = render_to_string('certificates/emails/certificate_notification.html', context)
        text_content = render_to_string('certificates/emails/certificate_notification.txt', context)
        
        # Envoi de l'email
        send_mail(
            subject=subject,
            message=text_content,
            html_message=html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[certificate.user.email],
            fail_silently=False
        )
        
        logger.info(f"Email de notification envoyé à {certificate.user.email}")
        
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de l'email de notification: {e}")


@receiver(post_save, sender=Certificate)
def log_certificate_creation(sender, instance, created, **kwargs):
    """Log la création de certificats pour audit"""
    
    if created:
        logger.info(
            f"Nouveau certificat créé: {instance.certificate_number} "
            f"pour {instance.user.username} - Cours: {instance.course_title}"
        )
        
        # Optionnel: enregistrer dans un système d'audit externe
        # audit_service.log_certificate_creation(instance)


@receiver(post_save, sender=Certificate)
def update_enrollment_certificate_status(sender, instance, created, **kwargs):
    """Met à jour le statut de l'inscription quand un certificat est créé"""
    
    if created and instance.enrollment:
        try:
            enrollment = instance.enrollment
            
            # Ajouter des métadonnées à l'inscription (si le champ existe)
            # Note: le modèle Enrollment n'a pas de champ metadata dans cette version
            # Cette fonctionnalité pourra être ajoutée ultérieurement si nécessaire
            logger.info(f"Certificat {instance.certificate_number} créé pour l'inscription {enrollment.id}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour des métadonnées: {e}")