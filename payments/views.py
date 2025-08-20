from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.utils.decorators import method_decorator
from django.views import View
from django.urls import reverse
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from .models import PaymentTransaction, PaymentConfiguration, WebhookEvent
from .services import NotchpayService, WebhookProcessor, get_notchpay_service
from courses.models import Course
import json
import logging

logger = logging.getLogger(__name__)


@login_required
def initiate_payment(request):
    """Vue pour initier un paiement"""
    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            amount = float(request.POST.get('amount'))
            currency = request.POST.get('currency', 'XAF')
            description = request.POST.get('description')
            return_url = request.POST.get('return_url')
            cancel_url = request.POST.get('cancel_url')
            
            # Informations du contenu payé (optionnel)
            content_type_id = request.POST.get('content_type_id')
            object_id = request.POST.get('object_id')
            
            # Valider les données
            if amount <= 0:
                messages.error(request, "Le montant doit être supérieur à zéro")
                return redirect(request.META.get('HTTP_REFERER', '/'))
            
            # Créer la transaction
            transaction = PaymentTransaction.objects.create(
                user=request.user,
                amount=amount,
                currency=currency,
                description=description,
                customer_name=request.user.get_full_name() or request.user.username,
                customer_email=request.user.email,
                customer_phone=getattr(request.user, 'phone', ''),
                return_url=return_url,
                cancel_url=cancel_url
            )
            
            # Associer le contenu payé si fourni
            if content_type_id and object_id:
                content_type = get_object_or_404(ContentType, id=content_type_id)
                transaction.content_type = content_type
                transaction.object_id = object_id
                transaction.save()
            
            # Initialiser le paiement avec Notchpay
            notchpay_service = get_notchpay_service()
            success, response_data = notchpay_service.initialize_payment(transaction)
            
            if success:
                # Rediriger vers l'URL d'autorisation Notchpay
                authorization_url = response_data.get('authorization_url')
                if authorization_url:
                    return redirect(authorization_url)
                else:
                    messages.error(request, "URL d'autorisation non reçue")
                    return redirect(request.META.get('HTTP_REFERER', '/'))
            else:
                error_message = response_data.get('message', 'Erreur lors de l\'initialisation du paiement')
                messages.error(request, error_message)
                return redirect(request.META.get('HTTP_REFERER', '/'))
                
        except ValueError:
            messages.error(request, "Montant invalide")
            return redirect(request.META.get('HTTP_REFERER', '/'))
        except Exception as e:
            logger.error(f"Erreur lors de l'initiation du paiement: {e}")
            messages.error(request, "Erreur lors de l'initiation du paiement")
            return redirect(request.META.get('HTTP_REFERER', '/'))
    
    return render(request, 'payments/initiate_payment.html')


@login_required
def course_order_summary(request, course_id):
    """Vue pour afficher le résumé de commande avant paiement"""
    course = get_object_or_404(Course, id=course_id)
    
    # Vérifier si l'utilisateur n'est pas déjà inscrit
    if request.user.enrolled_courses.filter(id=course.id).exists():
        messages.info(request, "Vous êtes déjà inscrit à ce cours")
        return redirect('courses:course_detail', course_id=course.id)
    
    # Vérifier si le cours est gratuit
    if course.price == 0:
        # Inscription directe pour les cours gratuits
        course.enrollments.create(user=request.user)
        messages.success(request, f"Vous êtes maintenant inscrit au cours {course.title}")
        return redirect('courses:course_detail', course_id=course.id)
    
    context = {
        'course': course,
        'payment_config': PaymentConfiguration.get_active_config()
    }
    return render(request, 'payments/order_summary.html', context)


@login_required
def course_payment(request, course_id):
    """Vue spécialisée pour le paiement d'un cours"""
    course = get_object_or_404(Course, id=course_id)
    
    # Vérifier si l'utilisateur n'est pas déjà inscrit
    if request.user.enrolled_courses.filter(id=course.id).exists():
        messages.info(request, "Vous êtes déjà inscrit à ce cours")
        return redirect('courses:course_detail', course_id=course.id)
    
    # Vérifier si le cours est gratuit
    if course.price == 0:
        # Inscription directe pour les cours gratuits
        course.enrollments.create(user=request.user)
        messages.success(request, f"Vous êtes maintenant inscrit au cours {course.title}")
        return redirect('courses:course_detail', course_id=course.id)
    
    if request.method == 'POST':
        try:
            # Créer la transaction pour le cours
            transaction = PaymentTransaction.objects.create(
                user=request.user,
                amount=course.price,
                currency='XAF',  # Devise par défaut
                description=f"Inscription au cours: {course.title}",
                customer_name=request.user.get_full_name() or request.user.username,
                customer_email=request.user.email,
                customer_phone=getattr(request.user, 'phone', ''),
                content_type=ContentType.objects.get_for_model(Course),
                object_id=str(course.id),
                return_url=request.build_absolute_uri(
                    reverse('payments:payment_success', args=['{transaction_id}'])
                ).replace('{transaction_id}', '{transaction_id}'),
                cancel_url=request.build_absolute_uri(
                    reverse('payments:payment_cancelled', args=['{transaction_id}'])
                ).replace('{transaction_id}', '{transaction_id}')
            )
            
            # Remplacer les placeholders avec l'ID réel de la transaction
            transaction.return_url = transaction.return_url.replace('{transaction_id}', str(transaction.id))
            transaction.cancel_url = transaction.cancel_url.replace('{transaction_id}', str(transaction.id))
            transaction.save()
            
            # Initialiser le paiement
            notchpay_service = get_notchpay_service()
            success, response_data = notchpay_service.initialize_payment(transaction)
            
            if success:
                authorization_url = response_data.get('authorization_url')
                if authorization_url:
                    return redirect(authorization_url)
                else:
                    messages.error(request, "URL d'autorisation non reçue")
                    return redirect('payments:payment_failure', transaction_id=transaction.id)
            else:
                error_message = response_data.get('message', 'Erreur lors de l\'initialisation du paiement')
                messages.error(request, error_message)
                return redirect('payments:payment_failure', transaction_id=transaction.id)
                
        except Exception as e:
            logger.error(f"Erreur lors du paiement du cours {course_id}: {e}")
            messages.error(request, "Erreur lors de l'initiation du paiement")
    
    context = {
        'course': course,
        'payment_config': PaymentConfiguration.get_active_config()
    }
    return render(request, 'payments/course_payment.html', context)


@login_required
def payment_success(request, transaction_id):
    """Vue de succès après paiement"""
    transaction = get_object_or_404(PaymentTransaction, id=transaction_id, user=request.user)
    
    # Vérifier le statut de la transaction avec Notchpay
    notchpay_service = get_notchpay_service()
    notchpay_service.update_transaction_status(transaction)
    
    # Traiter l'inscription au cours si applicable
    if transaction.is_successful and transaction.content_type:
        model_class = transaction.content_type.model_class()
        if model_class == Course:
            try:
                course = Course.objects.get(id=transaction.object_id)
                # Créer l'inscription si elle n'existe pas déjà
                enrollment, created = course.enrollments.get_or_create(user=request.user)
                if created:
                    messages.success(request, f"Inscription réussie au cours: {course.title}")
                else:
                    messages.info(request, "Vous étiez déjà inscrit à ce cours")
            except Course.DoesNotExist:
                logger.error(f"Cours {transaction.object_id} non trouvé après paiement réussi")
    
    context = {
        'transaction': transaction,
        'is_success': transaction.is_successful
    }
    return render(request, 'payments/payment_result.html', context)


@login_required
def payment_cancelled(request, transaction_id):
    """Vue d'annulation de paiement"""
    transaction = get_object_or_404(PaymentTransaction, id=transaction_id, user=request.user)
    
    # Mettre à jour le statut si ce n'est pas déjà fait
    if transaction.status == 'pending' or transaction.status == 'processing':
        transaction.status = 'cancelled'
        transaction.save()
    
    messages.warning(request, "Paiement annulé")
    
    context = {
        'transaction': transaction,
        'is_success': False
    }
    return render(request, 'payments/payment_result.html', context)


@login_required
def payment_failure(request, transaction_id):
    """Vue détaillée pour les échecs de paiement"""
    transaction = get_object_or_404(PaymentTransaction, id=transaction_id, user=request.user)
    
    # Vérifier que la transaction a effectivement échoué
    if not transaction.is_failed:
        return redirect('payments:payment_success', transaction_id=transaction.id)
    
    # Mettre à jour le statut avec Notchpay pour avoir les dernières informations
    notchpay_service = get_notchpay_service()
    notchpay_service.update_transaction_status(transaction)
    
    # Analyser le type d'erreur pour proposer des solutions appropriées
    error_suggestions = _get_error_suggestions(transaction)
    
    context = {
        'transaction': transaction,
        'error_suggestions': error_suggestions,
        'is_success': False
    }
    return render(request, 'payments/payment_failure.html', context)


def _get_error_suggestions(transaction):
    """Générer des suggestions basées sur le type d'erreur"""
    suggestions = []
    
    error_code = transaction.error_code or ''
    error_message = transaction.error_message or ''
    
    # Analyser les codes d'erreur courants
    if 'insufficient' in error_message.lower() or 'funds' in error_message.lower():
        suggestions.extend([
            "Vérifiez le solde de votre compte mobile money",
            "Rechargez votre compte et réessayez",
            "Essayez une autre méthode de paiement"
        ])
    elif 'invalid' in error_message.lower() or 'card' in error_message.lower():
        suggestions.extend([
            "Vérifiez les informations de votre carte bancaire",
            "Assurez-vous que votre carte n'a pas expiré",
            "Contactez votre banque pour autoriser la transaction"
        ])
    elif 'network' in error_message.lower() or 'timeout' in error_message.lower():
        suggestions.extend([
            "Vérifiez votre connexion internet",
            "Réessayez dans quelques minutes",
            "Utilisez une connexion plus stable"
        ])
    elif 'blocked' in error_message.lower() or 'restricted' in error_message.lower():
        suggestions.extend([
            "Contactez votre fournisseur de paiement",
            "Vérifiez les limites de votre compte",
            "Essayez une autre méthode de paiement"
        ])
    else:
        # Suggestions génériques
        suggestions.extend([
            "Vérifiez vos informations de paiement",
            "Essayez une autre méthode de paiement",
            "Contactez notre support si le problème persiste"
        ])
    
    return suggestions


@login_required
def transaction_detail(request, transaction_id):
    """Vue de détail d'une transaction"""
    transaction = get_object_or_404(PaymentTransaction, id=transaction_id, user=request.user)
    
    # Mettre à jour le statut si la transaction est en cours
    if transaction.is_pending:
        notchpay_service = get_notchpay_service()
        notchpay_service.update_transaction_status(transaction)
    
    context = {
        'transaction': transaction
    }
    return render(request, 'payments/transaction_detail.html', context)


@login_required
def user_transactions(request):
    """Vue listant les transactions de l'utilisateur"""
    transactions = PaymentTransaction.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'transactions': transactions
    }
    return render(request, 'payments/user_transactions.html', context)


@csrf_exempt
@require_POST
def webhook_endpoint(request):
    """Endpoint pour recevoir les webhooks de Notchpay"""
    try:
        # Récupérer les données du webhook
        payload = request.body.decode('utf-8')
        signature = request.META.get('HTTP_X_NOTCHPAY_SIGNATURE', '')
        
        if not signature:
            logger.warning("Webhook reçu sans signature")
            return HttpResponse('Missing signature', status=400)
        
        # Parser les données JSON
        try:
            event_data = json.loads(payload)
        except json.JSONDecodeError:
            logger.error("Webhook avec JSON invalide")
            return HttpResponse('Invalid JSON', status=400)
        
        # Traiter le webhook
        webhook_processor = WebhookProcessor()
        success = webhook_processor.process_webhook(event_data, signature)
        
        if success:
            logger.info(f"Webhook {event_data.get('id', 'unknown')} traité avec succès")
            return HttpResponse('OK', status=200)
        else:
            logger.error(f"Échec du traitement du webhook {event_data.get('id', 'unknown')}")
            return HttpResponse('Processing failed', status=500)
            
    except Exception as e:
        logger.error(f"Erreur lors du traitement du webhook: {e}")
        return HttpResponse('Internal error', status=500)


@require_http_methods(["GET"])
def check_transaction_status(request, transaction_id):
    """API endpoint pour vérifier le statut d'une transaction"""
    try:
        transaction = get_object_or_404(PaymentTransaction, id=transaction_id)
        
        # Vérifier les permissions
        if request.user != transaction.user and not request.user.is_staff:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        # Mettre à jour le statut avec Notchpay si nécessaire
        if transaction.is_pending:
            notchpay_service = get_notchpay_service()
            notchpay_service.update_transaction_status(transaction)
        
        return JsonResponse({
            'status': transaction.status,
            'is_successful': transaction.is_successful,
            'is_pending': transaction.is_pending,
            'is_failed': transaction.is_failed,
            'paid_at': transaction.paid_at.isoformat() if transaction.paid_at else None,
            'amount': str(transaction.amount),
            'currency': transaction.currency
        })
        
    except Exception as e:
        logger.error(f"Erreur lors de la vérification du statut: {e}")
        return JsonResponse({'error': 'Internal error'}, status=500)


class PaymentConfigurationView(View):
    """Vue pour la configuration des paiements (admin uniquement)"""
    
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, "Accès non autorisé")
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        """Affiche la configuration actuelle"""
        config = PaymentConfiguration.get_active_config()
        context = {
            'config': config,
            'environments': PaymentConfiguration.ENVIRONMENT_CHOICES
        }
        return render(request, 'payments/admin/configuration.html', context)
    
    def post(self, request):
        """Met à jour la configuration"""
        try:
            config = PaymentConfiguration.get_active_config()
            if not config:
                config = PaymentConfiguration()
            
            # Mettre à jour les champs
            config.environment = request.POST.get('environment', 'sandbox')
            config.public_key = request.POST.get('public_key', '')
            config.private_key = request.POST.get('private_key', '')
            config.webhook_secret = request.POST.get('webhook_secret', '')
            config.default_currency = request.POST.get('default_currency', 'XAF')
            config.timeout_seconds = int(request.POST.get('timeout_seconds', 30))
            config.max_retries = int(request.POST.get('max_retries', 3))
            config.is_active = True
            
            config.save()
            
            # Tester la connexion API
            notchpay_service = NotchpayService(config)
            success, response_data = notchpay_service.test_api_connection()
            
            if success:
                messages.success(request, "Configuration mise à jour et connexion API réussie")
            else:
                messages.warning(request, "Configuration mise à jour mais échec du test de connexion API")
            
        except ValueError as e:
            messages.error(request, f"Valeur invalide: {e}")
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de la configuration: {e}")
            messages.error(request, "Erreur lors de la mise à jour de la configuration")
        
        return redirect('payments:configuration')
