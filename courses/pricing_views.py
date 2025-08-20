"""
Vues pour la gestion des tarifications, bundles et codes promo
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, F
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
import json

from .models import (
    Course, CourseBundle, PromotionCode, PromotionCodeUsage, 
    Currency, PricingModel, ModulePricing
)
from .pricing_services import (
    pricing_calculator, trial_access_service, 
    installment_service, currency_service
)


@login_required
def course_pricing_detail(request, course_slug):
    """Page détaillée de tarification d'un cours"""
    course = get_object_or_404(Course, slug=course_slug, status='published')
    
    # Devise préférée de l'utilisateur
    user_currency = currency_service.get_user_preferred_currency(request.user)
    
    # Calculer le prix avec toutes les réductions
    pricing_info = pricing_calculator.get_course_price(
        course=course,
        currency_code=user_currency,
        user=request.user
    )
    
    # Vérifier accès essai gratuit
    trial_status = None
    if pricing_info['has_free_trial']:
        trial_active, trial_message = trial_access_service.check_trial_access(
            request.user, course
        )
        if trial_active:
            trial_status = trial_access_service.get_trial_progress(request.user, course)
    
    # Options de paiement échelonné
    installment_options = []
    if installment_service.can_pay_in_installments(course, request.user):
        max_installments = course.pricing_model.max_installments
        for i in range(2, max_installments + 1):
            installments = installment_service.calculate_installments(
                pricing_info['discounted_price'], i
            )
            installment_options.append({
                'num_installments': i,
                'installments': installments,
                'first_payment': installments[0] if installments else 0
            })
    
    # Modules individuels si disponible
    individual_modules = []
    if hasattr(course, 'pricing_model') and course.pricing_model.allow_individual_modules:
        for module in course.modules.filter(is_published=True):
            module_price = pricing_calculator.get_module_price(module, user_currency)
            if module_price:
                individual_modules.append({
                    'module': module,
                    'price': module_price,
                    'lessons_count': module.total_lessons
                })
    
    context = {
        'course': course,
        'pricing_info': pricing_info,
        'trial_status': trial_status,
        'installment_options': installment_options,
        'individual_modules': individual_modules,
        'user_currency': user_currency,
        'supported_currencies': currency_service.get_supported_currencies()
    }
    
    return render(request, 'courses/course_pricing_detail.html', context)


@login_required
def bundles_list(request):
    """Liste des bundles de cours disponibles"""
    # Filtres
    category = request.GET.get('category')
    min_savings = request.GET.get('min_savings')
    max_price = request.GET.get('max_price')
    
    # Query de base
    bundles = CourseBundle.objects.filter(
        is_active=True
    ).annotate(
        total_courses=Count('courses'),
        total_lessons=Sum('courses__modules__lessons')
    ).order_by('-savings_percentage')
    
    # Appliquer filtres
    if category:
        bundles = bundles.filter(courses__category__slug=category)
    
    if min_savings:
        try:
            bundles = bundles.filter(savings_percentage__gte=float(min_savings))
        except ValueError:
            pass
    
    if max_price:
        try:
            bundles = bundles.filter(price__lte=float(max_price))
        except ValueError:
            pass
    
    # Pagination
    paginator = Paginator(bundles, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Devise préférée
    user_currency = currency_service.get_user_preferred_currency(request.user)
    
    # Calculer prix pour chaque bundle
    bundles_with_pricing = []
    for bundle in page_obj:
        bundle_pricing = pricing_calculator.get_bundle_price(
            bundle=bundle,
            currency_code=user_currency,
            user=request.user
        )
        bundles_with_pricing.append({
            'bundle': bundle,
            'pricing': bundle_pricing
        })
    
    context = {
        'bundles_with_pricing': bundles_with_pricing,
        'page_obj': page_obj,
        'user_currency': user_currency,
        'filters': {
            'category': category,
            'min_savings': min_savings,
            'max_price': max_price
        }
    }
    
    return render(request, 'courses/bundles_list.html', context)


@login_required
def bundle_detail(request, bundle_slug):
    """Page détaillée d'un bundle"""
    bundle = get_object_or_404(CourseBundle, slug=bundle_slug, is_active=True)
    
    if not bundle.is_valid:
        messages.warning(request, "Ce bundle n'est plus disponible.")
        return redirect('courses:bundles_list')
    
    user_currency = currency_service.get_user_preferred_currency(request.user)
    
    # Calculer le prix du bundle
    bundle_pricing = pricing_calculator.get_bundle_price(
        bundle=bundle,
        currency_code=user_currency,
        user=request.user
    )
    
    # Détails des cours inclus
    courses_details = []
    for course in bundle.courses.all():
        course_pricing = pricing_calculator.get_course_price(
            course=course,
            currency_code=user_currency,
            user=request.user
        )
        courses_details.append({
            'course': course,
            'individual_price': course_pricing['discounted_price'],
            'modules_count': course.total_modules,
            'lessons_count': course.total_lessons
        })
    
    context = {
        'bundle': bundle,
        'bundle_pricing': bundle_pricing,
        'courses_details': courses_details,
        'user_currency': user_currency
    }
    
    return render(request, 'courses/bundle_detail.html', context)


@require_POST
@login_required
def apply_promotion_code(request):
    """API endpoint pour appliquer un code promo"""
    try:
        data = json.loads(request.body)
        code = data.get('code', '').strip().upper()
        course_id = data.get('course_id')
        bundle_id = data.get('bundle_id')
        
        if not code:
            return JsonResponse({'error': 'Code promo requis'}, status=400)
        
        # Récupérer le cours ou bundle
        course = None
        bundle = None
        
        if course_id:
            course = get_object_or_404(Course, id=course_id)
        elif bundle_id:
            bundle = get_object_or_404(CourseBundle, id=bundle_id)
        else:
            return JsonResponse({'error': 'Cours ou bundle requis'}, status=400)
        
        # Valider le code promo
        can_use, message = pricing_calculator.validate_promotion_code(
            code, request.user, course=course, bundle=bundle
        )
        
        if not can_use:
            return JsonResponse({'error': message}, status=400)
        
        # Calculer le nouveau prix
        if course:
            pricing_info = pricing_calculator.get_course_price(
                course=course,
                user=request.user,
                promotion_code=code
            )
        else:
            pricing_info = pricing_calculator.get_bundle_price(
                bundle=bundle,
                user=request.user,
                promotion_code=code
            )
        
        return JsonResponse({
            'success': True,
            'message': f'Code promo {code} appliqué avec succès',
            'original_price': float(pricing_info['original_price']),
            'discounted_price': float(pricing_info['discounted_price']),
            'discount_amount': float(pricing_info['discount_amount']),
            'currency': pricing_info['currency']
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Données JSON invalides'}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'Erreur serveur'}, status=500)


@require_POST
@login_required
def start_free_trial(request, course_id):
    """Commencer l'essai gratuit d'un cours"""
    course = get_object_or_404(Course, id=course_id, status='published')
    
    # Vérifier si le cours a un essai gratuit
    if not hasattr(course, 'pricing_model') or not course.pricing_model.has_free_trial:
        messages.error(request, "Ce cours n'offre pas d'essai gratuit.")
        return redirect('courses:detail', slug=course.slug)
    
    # Accorder l'accès d'essai
    success, message = trial_access_service.grant_trial_access(request.user, course)
    
    if success:
        messages.success(request, message)
        return redirect('courses:learn', slug=course.slug)
    else:
        messages.error(request, message)
        return redirect('courses:detail', slug=course.slug)


@login_required
def my_trials(request):
    """Page des essais gratuits de l'utilisateur"""
    from .models import Enrollment
    
    # Essais actifs
    active_trials = Enrollment.objects.filter(
        user=request.user,
        status='trial',
        trial_end_date__gt=timezone.now()
    ).select_related('course')
    
    # Essais expirés
    expired_trials = Enrollment.objects.filter(
        user=request.user,
        status__in=['expired', 'trial'],
        trial_end_date__lte=timezone.now()
    ).select_related('course')
    
    # Ajouter les informations de progression
    trials_with_progress = []
    for trial in active_trials:
        progress = trial_access_service.get_trial_progress(request.user, trial.course)
        trials_with_progress.append({
            'trial': trial,
            'progress': progress
        })
    
    context = {
        'active_trials': trials_with_progress,
        'expired_trials': expired_trials
    }
    
    return render(request, 'courses/my_trials.html', context)


@require_http_methods(["GET"])
def api_currency_rates(request):
    """API pour obtenir les taux de change actuels"""
    rates = {}
    base_currency = 'XAF'
    
    currencies = Currency.objects.filter(is_active=True)
    
    for currency in currencies:
        rates[currency.code] = {
            'name': currency.name,
            'symbol': currency.symbol,
            'rate': float(currency.exchange_rate_to_base)
        }
    
    return JsonResponse({
        'base_currency': base_currency,
        'rates': rates,
        'updated_at': timezone.now().isoformat()
    })


@require_http_methods(["GET"])
def api_course_price(request):
    """API pour calculer le prix d'un cours avec options"""
    course_id = request.GET.get('course_id')
    currency = request.GET.get('currency', 'XAF')
    promo_code = request.GET.get('promo_code')
    
    if not course_id:
        return JsonResponse({'error': 'Course ID required'}, status=400)
    
    try:
        course = Course.objects.get(id=course_id, status='published')
    except Course.DoesNotExist:
        return JsonResponse({'error': 'Course not found'}, status=404)
    
    user = request.user if request.user.is_authenticated else None
    
    pricing_info = pricing_calculator.get_course_price(
        course=course,
        currency_code=currency,
        user=user,
        promotion_code=promo_code
    )
    
    return JsonResponse(pricing_info)


@require_http_methods(["GET"])
def promotion_codes_list(request):
    """Liste publique des codes promo actifs (non-privés)"""
    now = timezone.now()
    
    # Codes promo publics (sans utilisateurs éligibles spécifiques)
    public_codes = PromotionCode.objects.filter(
        is_active=True,
        valid_from__lte=now,
        valid_until__gt=now
    ).filter(
        Q(eligible_users__isnull=True) | Q(eligible_users__exact=[])
    ).exclude(
        Q(max_uses__isnull=False) & Q(current_uses__gte=F('max_uses'))
    ).order_by('-discount_value')
    
    codes_info = []
    for code in public_codes[:10]:  # Limiter à 10 codes
        codes_info.append({
            'code': code.code,
            'name': code.name,
            'description': code.description,
            'discount_type': code.get_discount_type_display(),
            'discount_value': float(code.discount_value),
            'minimum_purchase': float(code.minimum_purchase_amount),
            'valid_until': code.valid_until.isoformat(),
            'new_users_only': code.new_users_only
        })
    
    return JsonResponse({
        'codes': codes_info,
        'count': len(codes_info)
    })


@login_required
def user_promotions_history(request):
    """Historique des codes promo utilisés par l'utilisateur"""
    usages = PromotionCodeUsage.objects.filter(
        user=request.user
    ).select_related('promotion_code', 'course', 'bundle').order_by('-used_at')
    
    paginator = Paginator(usages, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistiques
    total_savings = usages.aggregate(
        total=Sum('discount_amount')
    )['total'] or 0
    
    context = {
        'page_obj': page_obj,
        'total_savings': total_savings
    }
    
    return render(request, 'courses/user_promotions_history.html', context)