"""
Services pour la gestion de la tarification et des calculs de prix
"""
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q, Sum, F
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import (
    Course, Module, PricingModel, Currency, CourseBundle, 
    PromotionCode, PromotionCodeUsage, ModulePricing, PricingTier
)

User = get_user_model()


class PricingCalculatorService:
    """Service de calcul des prix avec promotions et devises"""
    
    def __init__(self):
        self.default_currency = 'XAF'
    
    def get_course_price(self, course, currency_code=None, user=None, promotion_code=None):
        """
        Calcule le prix final d'un cours avec toutes les réductions applicables
        
        Args:
            course: Instance de Course
            currency_code: Code de la devise (XAF, USD, EUR...)
            user: Utilisateur (pour les promotions personnalisées)
            promotion_code: Code promo à appliquer
            
        Returns:
            dict: {
                'original_price': Decimal,
                'discounted_price': Decimal, 
                'discount_amount': Decimal,
                'currency': str,
                'promotion_applied': str ou None,
                'has_free_trial': bool,
                'trial_info': dict ou None
            }
        """
        currency_code = currency_code or self.default_currency
        
        # Prix de base du cours
        if hasattr(course, 'pricing_model') and course.pricing_model:
            pricing_model = course.pricing_model
            original_price = pricing_model.get_price_for_currency(currency_code)
        else:
            # Fallback vers le prix simple du cours
            original_price = course.price or Decimal('0')
        
        result = {
            'original_price': original_price,
            'discounted_price': original_price,
            'discount_amount': Decimal('0'),
            'currency': currency_code,
            'promotion_applied': None,
            'has_free_trial': False,
            'trial_info': None
        }
        
        # Vérifier période d'essai gratuite
        if hasattr(course, 'pricing_model') and course.pricing_model:
            if course.pricing_model.has_free_trial:
                result['has_free_trial'] = True
                result['trial_info'] = {
                    'duration_days': course.pricing_model.trial_duration_days,
                    'access_type': course.pricing_model.get_trial_access_type_display()
                }
        
        # Si cours gratuit, pas de calcul nécessaire
        if original_price <= 0:
            return result
        
        # Appliquer réductions par niveau géographique
        if user:
            discount_from_tier = self._get_geographic_discount(user, original_price)
            if discount_from_tier > 0:
                result['discounted_price'] -= discount_from_tier
                result['discount_amount'] += discount_from_tier
        
        # Appliquer code promo
        if promotion_code and user:
            promo_discount = self._apply_promotion_code(
                promotion_code, course, user, result['discounted_price']
            )
            if promo_discount['valid']:
                result['discounted_price'] -= promo_discount['discount_amount']
                result['discount_amount'] += promo_discount['discount_amount']
                result['promotion_applied'] = promotion_code
        
        # S'assurer que le prix final n'est pas négatif
        result['discounted_price'] = max(result['discounted_price'], Decimal('0'))
        
        return result
    
    def get_module_price(self, module, currency_code=None):
        """Calcule le prix d'un module individuel"""
        currency_code = currency_code or self.default_currency
        
        # Vérifier si le module a une tarification individuelle
        if hasattr(module, 'individual_pricing'):
            return module.individual_pricing.price
        
        # Sinon, calculer basé sur le prix du cours
        course = module.course
        if hasattr(course, 'pricing_model') and course.pricing_model:
            if course.pricing_model.allow_individual_modules:
                return course.pricing_model.get_module_price(currency_code)
        
        return None
    
    def get_bundle_price(self, bundle, currency_code=None, user=None, promotion_code=None):
        """Calcule le prix d'un bundle avec réductions"""
        currency_code = currency_code or self.default_currency
        
        # Convertir le prix du bundle dans la devise demandée
        if bundle.currency.code != currency_code:
            converted_price = self._convert_currency(
                bundle.price, bundle.currency.code, currency_code
            )
        else:
            converted_price = bundle.price
        
        result = {
            'original_price': converted_price,
            'discounted_price': converted_price,
            'discount_amount': Decimal('0'),
            'currency': currency_code,
            'promotion_applied': None,
            'savings_vs_individual': bundle.savings_amount,
            'courses_included': bundle.courses_count
        }
        
        # Appliquer code promo si applicable
        if promotion_code and user:
            promo_discount = self._apply_promotion_code(
                promotion_code, None, user, converted_price, bundle=bundle
            )
            if promo_discount['valid']:
                result['discounted_price'] -= promo_discount['discount_amount']
                result['discount_amount'] += promo_discount['discount_amount']
                result['promotion_applied'] = promotion_code
        
        return result
    
    def _get_geographic_discount(self, user, original_price):
        """Applique les réductions géographiques basées sur le pays de l'utilisateur"""
        if not hasattr(user, 'profile') or not user.profile.country:
            return Decimal('0')
        
        try:
            tier = PricingTier.objects.filter(
                countries__contains=user.profile.country,
                is_active=True
            ).first()
            
            if tier and tier.discount_percentage > 0:
                return original_price * (tier.discount_percentage / 100)
        except:
            pass
        
        return Decimal('0')
    
    def _apply_promotion_code(self, code, course, user, current_price, bundle=None):
        """Applique un code promo et retourne les détails de la réduction"""
        try:
            promotion = PromotionCode.objects.get(code=code, is_active=True)
            
            # Vérifier validité
            can_use, message = promotion.can_be_used_by(user, course=course, bundle=bundle)
            if not can_use:
                return {'valid': False, 'message': message, 'discount_amount': Decimal('0')}
            
            # Calculer réduction
            discount_amount = promotion.calculate_discount(current_price)
            
            return {
                'valid': True,
                'discount_amount': discount_amount,
                'promotion': promotion
            }
            
        except PromotionCode.DoesNotExist:
            return {'valid': False, 'message': 'Code promo invalide', 'discount_amount': Decimal('0')}
    
    def _convert_currency(self, amount, from_currency, to_currency):
        """Convertit un montant d'une devise à une autre"""
        if from_currency == to_currency:
            return amount
        
        try:
            from_curr = Currency.objects.get(code=from_currency, is_active=True)
            to_curr = Currency.objects.get(code=to_currency, is_active=True)
            
            # Conversion via devise de base (XAF)
            base_amount = amount / from_curr.exchange_rate_to_base
            converted = base_amount * to_curr.exchange_rate_to_base
            
            return round(converted, 2)
        except Currency.DoesNotExist:
            return amount
    
    def validate_promotion_code(self, code, user, course=None, bundle=None):
        """Valide un code promo sans l'appliquer"""
        try:
            promotion = PromotionCode.objects.get(code=code)
            return promotion.can_be_used_by(user, course=course, bundle=bundle)
        except PromotionCode.DoesNotExist:
            return False, "Code promo non trouvé"


class TrialAccessService:
    """Service de gestion des accès d'essai gratuit"""
    
    def __init__(self):
        self.trial_model = 'courses.CourseTrialAccess'  # Modèle à créer
    
    def grant_trial_access(self, user, course):
        """Accorde l'accès d'essai à un utilisateur pour un cours"""
        if not hasattr(course, 'pricing_model') or not course.pricing_model:
            return False, "Pas de modèle de tarification défini"
        
        pricing = course.pricing_model
        if not pricing.has_free_trial:
            return False, "Pas d'essai gratuit disponible"
        
        # Vérifier si l'utilisateur a déjà utilisé son essai
        from .models import Enrollment
        existing_trial = Enrollment.objects.filter(
            user=user,
            course=course,
            status='trial'
        ).exists()
        
        if existing_trial:
            return False, "Essai gratuit déjà utilisé"
        
        # Créer inscription d'essai
        trial_end_date = timezone.now() + timedelta(days=pricing.trial_duration_days)
        
        enrollment = Enrollment.objects.create(
            user=user,
            course=course,
            status='trial',
            trial_end_date=trial_end_date
        )
        
        return True, f"Accès d'essai accordé pour {pricing.trial_duration_days} jours"
    
    def check_trial_access(self, user, course):
        """Vérifie le statut d'accès d'essai d'un utilisateur"""
        from .models import Enrollment
        
        try:
            enrollment = Enrollment.objects.get(user=user, course=course, status='trial')
            
            if enrollment.trial_end_date and timezone.now() > enrollment.trial_end_date:
                # Essai expiré
                enrollment.status = 'expired'
                enrollment.save()
                return False, "Période d'essai expirée"
            
            return True, "Accès d'essai actif"
        except Enrollment.DoesNotExist:
            return False, "Pas d'accès d'essai"
    
    def get_trial_progress(self, user, course):
        """Obtient les détails de progression de l'essai"""
        from .models import Enrollment
        
        try:
            enrollment = Enrollment.objects.get(user=user, course=course, status='trial')
            
            if not enrollment.trial_end_date:
                return None
            
            now = timezone.now()
            total_duration = enrollment.trial_end_date - enrollment.enrolled_at
            remaining_duration = enrollment.trial_end_date - now
            
            if remaining_duration.total_seconds() <= 0:
                return {
                    'status': 'expired',
                    'days_remaining': 0,
                    'progress_percentage': 100
                }
            
            progress = ((total_duration - remaining_duration) / total_duration) * 100
            
            return {
                'status': 'active',
                'days_remaining': remaining_duration.days,
                'hours_remaining': remaining_duration.seconds // 3600,
                'progress_percentage': round(progress, 1),
                'expires_at': enrollment.trial_end_date
            }
        except Enrollment.DoesNotExist:
            return None


class InstallmentService:
    """Service de gestion des paiements échelonnés"""
    
    def can_pay_in_installments(self, course, user=None):
        """Vérifie si un cours peut être payé en plusieurs fois"""
        if not hasattr(course, 'pricing_model') or not course.pricing_model:
            return False
        
        return course.pricing_model.supports_installments
    
    def calculate_installments(self, total_amount, num_installments, currency='XAF'):
        """Calcule les échéances de paiement"""
        if num_installments <= 1:
            return [total_amount]
        
        # Montant par échéance (arrondi)
        installment_amount = total_amount / num_installments
        installment_amount = round(installment_amount, 2)
        
        # Première échéance peut être légèrement différente pour éviter les erreurs d'arrondi
        installments = [installment_amount] * (num_installments - 1)
        first_installment = total_amount - (installment_amount * (num_installments - 1))
        installments.insert(0, first_installment)
        
        return installments
    
    def create_installment_plan(self, course, user, total_amount, num_installments):
        """Crée un plan de paiement échelonné"""
        if not self.can_pay_in_installments(course, user):
            raise ValidationError("Paiement échelonné non autorisé pour ce cours")
        
        max_installments = course.pricing_model.max_installments
        if num_installments > max_installments:
            raise ValidationError(f"Maximum {max_installments} échéances autorisées")
        
        installments = self.calculate_installments(total_amount, num_installments)
        
        # Calculer les dates d'échéance (mensuel)
        plan = []
        for i, amount in enumerate(installments):
            due_date = timezone.now() + timedelta(days=30 * i)  # Tous les mois
            plan.append({
                'installment_number': i + 1,
                'amount': amount,
                'due_date': due_date,
                'status': 'pending' if i > 0 else 'current'
            })
        
        return plan


class CurrencyService:
    """Service de gestion des devises"""
    
    def get_supported_currencies(self):
        """Retourne la liste des devises supportées"""
        return Currency.objects.filter(is_active=True).order_by('name')
    
    def get_user_preferred_currency(self, user):
        """Détermine la devise préférée d'un utilisateur basée sur son profil"""
        if hasattr(user, 'profile') and user.profile.preferred_currency:
            return user.profile.preferred_currency
        
        # Devise basée sur le pays
        country_currencies = {
            'CM': 'XAF',  # Cameroun
            'SN': 'XOF',  # Sénégal
            'CI': 'XOF',  # Côte d'Ivoire
            'FR': 'EUR',  # France
            'US': 'USD',  # États-Unis
            'CA': 'CAD',  # Canada
        }
        
        if hasattr(user, 'profile') and user.profile.country:
            return country_currencies.get(user.profile.country, 'XAF')
        
        return 'XAF'  # Devise par défaut
    
    def update_exchange_rates(self):
        """Met à jour les taux de change (à connecter avec une API externe)"""
        # Placeholder - à implémenter avec une API comme fixer.io ou CurrencyLayer
        pass
    
    def format_price(self, amount, currency_code):
        """Formate un prix selon la devise"""
        currency = Currency.objects.filter(code=currency_code).first()
        if not currency:
            return f"{amount}"
        
        # Formatage selon la devise
        if currency_code in ['XAF', 'XOF']:
            return f"{amount:,.0f} {currency.symbol}"
        elif currency_code in ['USD', 'CAD']:
            return f"{currency.symbol}{amount:,.2f}"
        elif currency_code == 'EUR':
            return f"{amount:,.2f} {currency.symbol}"
        else:
            return f"{amount:,.2f} {currency.symbol}"


# Instances globales des services
pricing_calculator = PricingCalculatorService()
trial_access_service = TrialAccessService()
installment_service = InstallmentService()
currency_service = CurrencyService()