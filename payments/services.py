"""
Service layer pour l'intégration Notchpay
"""
import requests
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import PaymentTransaction, PaymentConfiguration, WebhookEvent
import logging

logger = logging.getLogger(__name__)


class NotchpayAPIError(Exception):
    """Exception personnalisée pour les erreurs API Notchpay"""
    def __init__(self, message: str, status_code: int = None, response_data: dict = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}
        super().__init__(self.message)


class NotchpayTimeoutError(NotchpayAPIError):
    """Exception pour les timeouts d'API Notchpay"""
    pass


class NotchpayService:
    """Service principal pour les interactions avec l'API Notchpay"""
    
    # URLs de base des APIs
    SANDBOX_BASE_URL = "https://api.notchpay.co/sandbox/v1"
    PRODUCTION_BASE_URL = "https://api.notchpay.co/v1"
    
    def __init__(self, config: PaymentConfiguration = None):
        """
        Initialise le service avec une configuration
        """
        if config is None:
            config = PaymentConfiguration.get_active_config()
            
        if not config:
            raise ValidationError("Aucune configuration de paiement active trouvée")
            
        self.config = config
        self.base_url = self.SANDBOX_BASE_URL if config.is_sandbox else self.PRODUCTION_BASE_URL
        self.headers = {
            'Authorization': f'Bearer {config.private_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: dict = None,
        timeout: int = None
    ) -> Tuple[bool, dict]:
        """
        Effectue une requête HTTP vers l'API Notchpay avec gestion d'erreurs
        
        Returns:
            Tuple[bool, dict]: (succès, données_réponse)
        """
        timeout = timeout or self.config.timeout_seconds
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            logger.info(f"Notchpay API Request: {method} {url}")
            
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                timeout=timeout
            )
            
            response_data = {}
            try:
                response_data = response.json()
            except ValueError:
                response_data = {'raw_response': response.text}
            
            logger.info(f"Notchpay API Response: {response.status_code} - {response_data}")
            
            # Gestion des codes de statut
            if response.status_code == 200:
                return True, response_data
            elif response.status_code == 201:
                return True, response_data
            elif response.status_code >= 400:
                error_message = response_data.get('message', 'Erreur API inconnue')
                raise NotchpayAPIError(
                    message=error_message,
                    status_code=response.status_code,
                    response_data=response_data
                )
            else:
                return False, response_data
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout lors de la requête vers {url}")
            raise NotchpayTimeoutError(f"Timeout après {timeout} secondes")
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Erreur de connexion vers {url}: {e}")
            raise NotchpayAPIError(f"Erreur de connexion: {e}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur de requête vers {url}: {e}")
            raise NotchpayAPIError(f"Erreur de requête: {e}")
    
    def initialize_payment(
        self, 
        transaction: PaymentTransaction
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Initialise un paiement avec Notchpay
        
        Args:
            transaction: Instance de PaymentTransaction
            
        Returns:
            Tuple[bool, dict]: (succès, données_réponse)
        """
        try:
            # Préparer les données de paiement
            payment_data = {
                'amount': int(transaction.amount_in_cents),
                'currency': transaction.currency,
                'description': transaction.description,
                'reference': transaction.reference,
                'callback': self.config.webhook_url,
                'return_url': transaction.return_url or self.config.default_return_url,
                'cancel_url': transaction.cancel_url or self.config.default_cancel_url,
                'customer': {
                    'name': transaction.customer_name,
                    'email': transaction.customer_email,
                    'phone': transaction.customer_phone
                },
                'metadata': transaction.metadata
            }
            
            # Ajouter la méthode de paiement si spécifiée
            if transaction.payment_method:
                payment_data['payment_method'] = transaction.payment_method
            
            logger.info(f"Initialisation paiement pour transaction {transaction.reference}")
            
            # Effectuer la requête
            success, response_data = self._make_request(
                method='POST',
                endpoint='/payments/initialize',
                data=payment_data
            )
            
            if success:
                # Mettre à jour la transaction avec les données de réponse
                transaction.notchpay_transaction_id = response_data.get('transaction_id')
                transaction.authorization_url = response_data.get('authorization_url')
                transaction.notchpay_response = response_data
                transaction.status = 'processing'
                transaction.save()
                
                logger.info(f"Paiement initialisé avec succès: {transaction.notchpay_transaction_id}")
                
            return success, response_data
            
        except NotchpayAPIError as e:
            logger.error(f"Erreur API lors de l'initialisation: {e.message}")
            transaction.mark_as_failed(
                error_code=str(e.status_code) if e.status_code else 'API_ERROR',
                error_message=e.message
            )
            return False, e.response_data
            
        except Exception as e:
            logger.error(f"Erreur inattendue lors de l'initialisation: {e}")
            transaction.mark_as_failed(
                error_code='UNEXPECTED_ERROR',
                error_message=str(e)
            )
            return False, {'error': str(e)}
    
    def verify_transaction(self, transaction_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Vérifie le statut d'une transaction auprès de Notchpay
        
        Args:
            transaction_id: ID de transaction Notchpay
            
        Returns:
            Tuple[bool, dict]: (succès, données_réponse)
        """
        try:
            logger.info(f"Vérification du statut de la transaction {transaction_id}")
            
            success, response_data = self._make_request(
                method='GET',
                endpoint=f'/payments/{transaction_id}/verify'
            )
            
            if success:
                logger.info(f"Statut vérifié: {response_data.get('status')}")
            
            return success, response_data
            
        except NotchpayAPIError as e:
            logger.error(f"Erreur lors de la vérification: {e.message}")
            return False, e.response_data
            
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la vérification: {e}")
            return False, {'error': str(e)}
    
    def update_transaction_status(self, transaction: PaymentTransaction) -> bool:
        """
        Met à jour le statut d'une transaction locale en vérifiant avec Notchpay
        
        Args:
            transaction: Instance de PaymentTransaction
            
        Returns:
            bool: True si la mise à jour a réussi
        """
        if not transaction.notchpay_transaction_id:
            logger.warning(f"Pas d'ID Notchpay pour la transaction {transaction.reference}")
            return False
        
        try:
            success, response_data = self.verify_transaction(transaction.notchpay_transaction_id)
            
            if success:
                # Mapper les statuts Notchpay vers nos statuts internes
                notchpay_status = response_data.get('status', '').lower()
                status_mapping = {
                    'successful': 'completed',
                    'completed': 'completed',
                    'failed': 'failed',
                    'cancelled': 'cancelled',
                    'expired': 'expired',
                    'pending': 'pending',
                    'processing': 'processing'
                }
                
                new_status = status_mapping.get(notchpay_status, transaction.status)
                
                # Mettre à jour la transaction si le statut a changé
                if new_status != transaction.status:
                    transaction.status = new_status
                    transaction.notchpay_response.update(response_data)
                    
                    if new_status == 'completed':
                        transaction.paid_at = timezone.now()
                        
                        # Calculer les frais et le montant net
                        fees = response_data.get('fees', 0)
                        if fees:
                            transaction.processing_fee = fees / 100  # Convertir en unité principale
                            transaction.net_amount = transaction.amount - transaction.processing_fee
                    
                    transaction.save()
                    logger.info(f"Transaction {transaction.reference} mise à jour: {new_status}")
                    
                return True
                
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du statut: {e}")
            return False
        
        return False
    
    def create_refund(
        self, 
        transaction: PaymentTransaction, 
        amount: float = None, 
        reason: str = ""
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Crée un remboursement pour une transaction
        
        Args:
            transaction: Instance de PaymentTransaction
            amount: Montant à rembourser (None = remboursement total)
            reason: Raison du remboursement
            
        Returns:
            Tuple[bool, dict]: (succès, données_réponse)
        """
        if not transaction.is_successful:
            raise ValidationError("Impossible de rembourser une transaction non réussie")
        
        if not transaction.notchpay_transaction_id:
            raise ValidationError("Pas d'ID Notchpay pour cette transaction")
        
        refund_amount = amount or transaction.amount
        
        try:
            refund_data = {
                'transaction_id': transaction.notchpay_transaction_id,
                'amount': int(refund_amount * 100),  # Convertir en centimes
                'reason': reason
            }
            
            logger.info(f"Création d'un remboursement de {refund_amount} pour {transaction.reference}")
            
            success, response_data = self._make_request(
                method='POST',
                endpoint='/refunds',
                data=refund_data
            )
            
            if success:
                # Créer l'instance de remboursement
                from .models import PaymentRefund
                refund = PaymentRefund.objects.create(
                    transaction=transaction,
                    notchpay_refund_id=response_data.get('refund_id'),
                    amount=refund_amount,
                    reason=reason,
                    status='processing',
                    notchpay_response=response_data
                )
                
                logger.info(f"Remboursement créé: {refund.id}")
            
            return success, response_data
            
        except NotchpayAPIError as e:
            logger.error(f"Erreur lors de la création du remboursement: {e.message}")
            return False, e.response_data
            
        except Exception as e:
            logger.error(f"Erreur inattendue lors du remboursement: {e}")
            return False, {'error': str(e)}
    
    def verify_webhook_signature(self, payload: str, signature: str) -> bool:
        """
        Vérifie la signature d'un webhook Notchpay
        
        Args:
            payload: Corps de la requête webhook (JSON string)
            signature: Signature fournie dans les headers
            
        Returns:
            bool: True si la signature est valide
        """
        if not self.config.webhook_secret:
            logger.warning("Pas de secret webhook configuré")
            return False
        
        try:
            # Calculer la signature attendue
            expected_signature = hmac.new(
                self.config.webhook_secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Comparer les signatures
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de signature: {e}")
            return False
    
    def test_api_connection(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Teste la connexion à l'API Notchpay
        
        Returns:
            Tuple[bool, dict]: (succès, données_réponse)
        """
        try:
            logger.info("Test de connexion à l'API Notchpay")
            
            success, response_data = self._make_request(
                method='GET',
                endpoint='/ping',
                timeout=10
            )
            
            if success:
                logger.info("Connexion API réussie")
            else:
                logger.warning("Échec du test de connexion")
            
            return success, response_data
            
        except Exception as e:
            logger.error(f"Erreur lors du test de connexion: {e}")
            return False, {'error': str(e)}


class WebhookProcessor:
    """Processeur pour les événements webhook de Notchpay"""
    
    def __init__(self, notchpay_service: NotchpayService = None):
        self.notchpay_service = notchpay_service or NotchpayService()
    
    def process_webhook(self, event_data: dict, signature: str) -> bool:
        """
        Traite un événement webhook
        
        Args:
            event_data: Données de l'événement
            signature: Signature de vérification
            
        Returns:
            bool: True si le traitement a réussi
        """
        try:
            # Vérifier la signature
            payload = json.dumps(event_data, separators=(',', ':'))
            if not self.notchpay_service.verify_webhook_signature(payload, signature):
                logger.error("Signature webhook invalide")
                return False
            
            # Créer l'événement webhook
            webhook_event = WebhookEvent.objects.create(
                event_id=event_data.get('id'),
                event_type=event_data.get('event'),
                data=event_data,
                signature=signature
            )
            
            try:
                # Traiter l'événement selon son type
                event_type = event_data.get('event')
                transaction_data = event_data.get('data', {})
                
                if event_type == 'payment.completed':
                    self._handle_payment_completed(transaction_data, webhook_event)
                elif event_type == 'payment.failed':
                    self._handle_payment_failed(transaction_data, webhook_event)
                elif event_type == 'payment.cancelled':
                    self._handle_payment_cancelled(transaction_data, webhook_event)
                elif event_type == 'refund.completed':
                    self._handle_refund_completed(transaction_data, webhook_event)
                else:
                    logger.warning(f"Type d'événement non géré: {event_type}")
                
                webhook_event.mark_as_processed()
                return True
                
            except Exception as e:
                webhook_event.error_message = str(e)
                webhook_event.save()
                logger.error(f"Erreur lors du traitement de l'événement {webhook_event.event_id}: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Erreur lors du traitement du webhook: {e}")
            return False
    
    def _handle_payment_completed(self, transaction_data: dict, webhook_event: WebhookEvent):
        """Gère l'événement de paiement terminé"""
        reference = transaction_data.get('reference')
        if not reference:
            logger.error("Pas de référence dans l'événement payment.completed")
            return
        
        try:
            transaction = PaymentTransaction.objects.get(reference=reference)
            transaction.mark_as_completed(transaction_data)
            webhook_event.transaction = transaction
            webhook_event.save()
            
            logger.info(f"Paiement {reference} marqué comme terminé via webhook")
            
        except PaymentTransaction.DoesNotExist:
            logger.error(f"Transaction {reference} non trouvée pour l'événement webhook")
    
    def _handle_payment_failed(self, transaction_data: dict, webhook_event: WebhookEvent):
        """Gère l'événement de paiement échoué"""
        reference = transaction_data.get('reference')
        if not reference:
            logger.error("Pas de référence dans l'événement payment.failed")
            return
        
        try:
            transaction = PaymentTransaction.objects.get(reference=reference)
            error_message = transaction_data.get('failure_reason', 'Paiement échoué')
            transaction.mark_as_failed(
                error_code='PAYMENT_FAILED',
                error_message=error_message
            )
            webhook_event.transaction = transaction
            webhook_event.save()
            
            logger.info(f"Paiement {reference} marqué comme échoué via webhook")
            
        except PaymentTransaction.DoesNotExist:
            logger.error(f"Transaction {reference} non trouvée pour l'événement webhook")
    
    def _handle_payment_cancelled(self, transaction_data: dict, webhook_event: WebhookEvent):
        """Gère l'événement de paiement annulé"""
        reference = transaction_data.get('reference')
        if not reference:
            logger.error("Pas de référence dans l'événement payment.cancelled")
            return
        
        try:
            transaction = PaymentTransaction.objects.get(reference=reference)
            transaction.status = 'cancelled'
            transaction.save()
            webhook_event.transaction = transaction
            webhook_event.save()
            
            logger.info(f"Paiement {reference} marqué comme annulé via webhook")
            
        except PaymentTransaction.DoesNotExist:
            logger.error(f"Transaction {reference} non trouvée pour l'événement webhook")
    
    def _handle_refund_completed(self, refund_data: dict, webhook_event: WebhookEvent):
        """Gère l'événement de remboursement terminé"""
        refund_id = refund_data.get('refund_id')
        if not refund_id:
            logger.error("Pas d'ID de remboursement dans l'événement refund.completed")
            return
        
        try:
            from .models import PaymentRefund
            refund = PaymentRefund.objects.get(notchpay_refund_id=refund_id)
            refund.status = 'completed'
            refund.processed_at = timezone.now()
            refund.notchpay_response.update(refund_data)
            refund.save()
            
            webhook_event.transaction = refund.transaction
            webhook_event.save()
            
            logger.info(f"Remboursement {refund_id} marqué comme terminé via webhook")
            
        except PaymentRefund.DoesNotExist:
            logger.error(f"Remboursement {refund_id} non trouvé pour l'événement webhook")


# Instance globale du service (sera initialisée au premier usage)
_notchpay_service = None

def get_notchpay_service() -> NotchpayService:
    """Retourne une instance du service Notchpay"""
    global _notchpay_service
    if _notchpay_service is None:
        _notchpay_service = NotchpayService()
    return _notchpay_service