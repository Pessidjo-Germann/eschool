from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    SystemConfiguration, ModerationLog, PlatformStatistics, 
    PaymentDispute, AdminActivity
)
from courses.models import Course
from payments.models import PaymentTransaction
from quiz.models import QuizAttempt

User = get_user_model()

def is_superadmin(user):
    return user.is_authenticated and user.is_superuser

@login_required
@user_passes_test(is_superadmin)
def dashboard(request):
    """Dashboard principal des super-admins"""
    # Statistiques générales
    today = timezone.now().date()
    stats = {
        'total_users': User.objects.count(),
        'new_users_today': User.objects.filter(date_joined__date=today).count(),
        'total_courses': Course.objects.count(),
        'published_courses': Course.objects.filter(is_published=True).count(),
        'pending_moderation': Course.objects.filter(is_published=False).count(),
        'total_revenue': PaymentTransaction.objects.filter(
            status='completed'
        ).aggregate(Sum('amount'))['amount__sum'] or 0,
        'open_disputes': PaymentDispute.objects.filter(status='open').count(),
    }
    
    # Activités récentes
    recent_activities = AdminActivity.objects.select_related('admin')[:10]
    
    # Litiges récents
    recent_disputes = PaymentDispute.objects.select_related('user')[:5]
    
    context = {
        'stats': stats,
        'recent_activities': recent_activities,
        'recent_disputes': recent_disputes,
    }
    
    return render(request, 'superadmin/dashboard.html', context)

@login_required
@user_passes_test(is_superadmin)
def user_management(request):
    """Gestion de tous les utilisateurs"""
    search = request.GET.get('search', '')
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    
    users = User.objects.all()
    
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    if role_filter:
        if role_filter == 'instructor':
            users = users.filter(role='instructor')
        elif role_filter == 'student':
            users = users.filter(role='student')
        elif role_filter == 'admin':
            users = users.filter(is_staff=True)
    
    if status_filter:
        if status_filter == 'active':
            users = users.filter(is_active=True)
        elif status_filter == 'inactive':
            users = users.filter(is_active=False)
    
    paginator = Paginator(users, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'role_filter': role_filter,
        'status_filter': status_filter,
    }
    
    return render(request, 'superadmin/user_management.html', context)

@login_required
@user_passes_test(is_superadmin)
def user_detail(request, user_id):
    """Détails et actions sur un utilisateur"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'toggle_active':
            user.is_active = not user.is_active
            user.save()
            
            # Log de l'activité
            AdminActivity.objects.create(
                admin=request.user,
                action=f"{'Activate' if user.is_active else 'Deactivate'} user",
                description=f"User {user.username} was {'activated' if user.is_active else 'deactivated'}",
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            messages.success(request, f"Utilisateur {'activé' if user.is_active else 'désactivé'} avec succès")
        
        elif action == 'make_instructor':
            user.role = 'instructor'
            user.save()
            
            AdminActivity.objects.create(
                admin=request.user,
                action="Change user role",
                description=f"User {user.username} promoted to instructor",
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            messages.success(request, "Utilisateur promu formateur avec succès")
        
        return redirect('superadmin:user_detail', user_id=user.id)
    
    # Statistiques utilisateur
    user_stats = {
        'courses_enrolled': user.enrollments.count() if hasattr(user, 'enrollments') else 0,
        'courses_created': user.courses.count() if hasattr(user, 'courses') else 0,
        'total_spent': user.payment_transactions.filter(
            status='completed'
        ).aggregate(Sum('amount'))['amount__sum'] or 0,
        'quiz_attempts': QuizAttempt.objects.filter(user=user).count(),
    }
    
    # PaymentTransactions récentes
    recent_transactions = user.payment_transactions.all()[:10]
    
    context = {
        'user_obj': user,
        'user_stats': user_stats,
        'recent_transactions': recent_transactions,
    }
    
    return render(request, 'superadmin/user_detail.html', context)

@login_required
@user_passes_test(is_superadmin)
def content_moderation(request):
    """Interface de modération de contenu"""
    content_type = request.GET.get('type', 'courses')
    
    if content_type == 'courses':
        items = Course.objects.filter(is_published=False).order_by('-created_at')
    else:
        items = []
    
    paginator = Paginator(items, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'content_type': content_type,
    }
    
    return render(request, 'superadmin/content_moderation.html', context)

@login_required
@user_passes_test(is_superadmin)
def moderate_content(request, content_type, content_id):
    """Modérer un contenu spécifique"""
    if content_type == 'course':
        content = get_object_or_404(Course, id=content_id)
        
        if request.method == 'POST':
            action = request.POST.get('action')
            reason = request.POST.get('reason', '')
            
            if action == 'approve':
                content.is_published = True
                content.save()
                
                ModerationLog.objects.create(
                    moderator=request.user,
                    action='approve',
                    reason=reason,
                    content_object=content
                )
                
                messages.success(request, "Cours approuvé avec succès")
            
            elif action == 'reject':
                ModerationLog.objects.create(
                    moderator=request.user,
                    action='reject',
                    reason=reason,
                    content_object=content
                )
                
                messages.success(request, "Cours rejeté avec succès")
            
            return redirect('superadmin:content_moderation')
    
    context = {
        'content': content,
        'content_type': content_type,
    }
    
    return render(request, 'superadmin/moderate_content.html', context)

@login_required
@user_passes_test(is_superadmin)
def platform_statistics(request):
    """Statistiques globales de la plateforme"""
    # Période sélectionnée
    period = request.GET.get('period', '7d')
    
    if period == '7d':
        start_date = timezone.now().date() - timedelta(days=7)
    elif period == '30d':
        start_date = timezone.now().date() - timedelta(days=30)
    elif period == '90d':
        start_date = timezone.now().date() - timedelta(days=90)
    else:
        start_date = timezone.now().date() - timedelta(days=7)
    
    # Statistiques utilisateurs
    user_stats = {
        'total': User.objects.count(),
        'new': User.objects.filter(date_joined__date__gte=start_date).count(),
        'active': User.objects.filter(
            last_login__date__gte=start_date
        ).count(),
        'by_role': User.objects.values('role').annotate(count=Count('id'))
    }
    
    # Statistiques cours
    course_stats = {
        'total': Course.objects.count(),
        'published': Course.objects.filter(is_published=True).count(),
        'new': Course.objects.filter(created_at__date__gte=start_date).count(),
    }
    
    # Statistiques financières
    financial_stats = {
        'total_revenue': PaymentTransaction.objects.filter(
            status='completed'
        ).aggregate(Sum('amount'))['amount__sum'] or 0,
        'period_revenue': PaymentTransaction.objects.filter(
            status='completed',
            created_at__date__gte=start_date
        ).aggregate(Sum('amount'))['amount__sum'] or 0,
        'total_transactions': PaymentTransaction.objects.filter(
            status='completed'
        ).count(),
        'success_rate': 0,
    }
    
    total_attempts = PaymentTransaction.objects.count()
    if total_attempts > 0:
        successful = PaymentTransaction.objects.filter(status='completed').count()
        financial_stats['success_rate'] = (successful / total_attempts) * 100
    
    context = {
        'period': period,
        'user_stats': user_stats,
        'course_stats': course_stats,
        'financial_stats': financial_stats,
    }
    
    return render(request, 'superadmin/platform_statistics.html', context)

@login_required
@user_passes_test(is_superadmin)
def payment_disputes(request):
    """Gestion des litiges de paiement"""
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    disputes = PaymentDispute.objects.select_related('user', 'assigned_to')
    
    if status_filter:
        disputes = disputes.filter(status=status_filter)
    
    if search:
        disputes = disputes.filter(
            Q(transaction_id__icontains=search) |
            Q(user__username__icontains=search) |
            Q(description__icontains=search)
        )
    
    paginator = Paginator(disputes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'search': search,
    }
    
    return render(request, 'superadmin/payment_disputes.html', context)

@login_required
@user_passes_test(is_superadmin)
def dispute_detail(request, dispute_id):
    """Détails et gestion d'un litige"""
    dispute = get_object_or_404(PaymentDispute, id=dispute_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'assign':
            dispute.assigned_to = request.user
            dispute.status = 'investigating'
            dispute.save()
            
            messages.success(request, "Litige assigné avec succès")
        
        elif action == 'resolve':
            dispute.status = 'resolved'
            dispute.resolution_notes = request.POST.get('resolution_notes', '')
            dispute.resolved_at = timezone.now()
            dispute.save()
            
            AdminActivity.objects.create(
                admin=request.user,
                action="Resolve payment dispute",
                description=f"Dispute #{dispute.id} resolved for transaction {dispute.transaction_id}",
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            messages.success(request, "Litige résolu avec succès")
        
        return redirect('superadmin:dispute_detail', dispute_id=dispute.id)
    
    context = {
        'dispute': dispute,
    }
    
    return render(request, 'superadmin/dispute_detail.html', context)

@login_required
@user_passes_test(is_superadmin)
def system_configuration(request):
    """Configuration système"""
    configs = SystemConfiguration.objects.all().order_by('key')
    
    if request.method == 'POST':
        key = request.POST.get('key')
        value = request.POST.get('value')
        description = request.POST.get('description', '')
        
        config, created = SystemConfiguration.objects.get_or_create(
            key=key,
            defaults={
                'value': value,
                'description': description,
                'updated_by': request.user
            }
        )
        
        if not created:
            config.value = value
            config.description = description
            config.updated_by = request.user
            config.save()
        
        AdminActivity.objects.create(
            admin=request.user,
            action="Update system configuration",
            description=f"Configuration '{key}' updated",
            ip_address=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        messages.success(request, "Configuration mise à jour avec succès")
        return redirect('superadmin:system_configuration')
    
    context = {
        'configs': configs,
    }
    
    return render(request, 'superadmin/system_configuration.html', context)

@login_required
@user_passes_test(is_superadmin)
def api_statistics(request):
    """API pour les statistiques du dashboard"""
    period = request.GET.get('period', '7d')
    
    if period == '7d':
        days = 7
    elif period == '30d':
        days = 30
    else:
        days = 7
    
    # Données pour les graphiques
    dates = []
    user_counts = []
    revenue_data = []
    
    for i in range(days):
        date = timezone.now().date() - timedelta(days=i)
        dates.append(date.strftime('%Y-%m-%d'))
        
        # Nouveaux utilisateurs par jour
        new_users = User.objects.filter(date_joined__date=date).count()
        user_counts.append(new_users)
        
        # Revenus par jour
        daily_revenue = PaymentTransaction.objects.filter(
            status='completed',
            created_at__date=date
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        revenue_data.append(float(daily_revenue))
    
    data = {
        'dates': list(reversed(dates)),
        'new_users': list(reversed(user_counts)),
        'daily_revenue': list(reversed(revenue_data)),
    }
    
    return JsonResponse(data)
