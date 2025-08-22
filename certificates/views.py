from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, JsonResponse, Http404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_http_methods
import logging

from .models import Certificate, CertificateTemplate, CertificateShare
from .services import certificate_generator
from courses.models import Enrollment

logger = logging.getLogger(__name__)


@login_required
def my_certificates(request):
    """Vue des certificats de l'utilisateur connecté"""
    certificates = Certificate.objects.filter(
        user=request.user,
        status__in=['generated', 'issued']
    ).select_related('course', 'template').order_by('-created_at')
    
    # Pagination
    paginator = Paginator(certificates, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistiques
    stats = {
        'total_certificates': certificates.count(),
        'recent_certificates': certificates.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=30)
        ).count(),
    }
    
    context = {
        'page_obj': page_obj,
        'certificates': page_obj,
        'stats': stats,
    }
    
    return render(request, 'certificates/my_certificates.html', context)


@login_required
def certificate_detail(request, certificate_id):
    """Vue détaillée d'un certificat"""
    certificate = get_object_or_404(
        Certificate.objects.select_related('course', 'template', 'enrollment'),
        id=certificate_id,
        user=request.user
    )
    
    # Vérifier si le certificat est valide
    if not certificate.is_valid():
        messages.error(request, "Ce certificat n'est plus valide.")
    
    # Obtenir ou créer un lien de partage si demandé
    share_link = None
    if request.GET.get('create_share') == '1':
        share, created = CertificateShare.objects.get_or_create(
            certificate=certificate,
            defaults={'expires_at': timezone.now() + timezone.timedelta(days=365)}
        )
        share_link = request.build_absolute_uri(share.get_share_url())
        if created:
            messages.success(request, "Lien de partage créé avec succès!")
    
    context = {
        'certificate': certificate,
        'share_link': share_link,
    }
    
    return render(request, 'certificates/certificate_detail.html', context)


def verify_certificate(request, hash):
    """Vérification publique d'un certificat via son hash"""
    try:
        certificate = get_object_or_404(
            Certificate.objects.select_related('course', 'user'),
            verification_hash=hash
        )
        
        if not certificate.is_valid():
            context = {
                'error': 'Ce certificat n\'est plus valide ou a été révoqué.',
                'certificate': certificate
            }
            return render(request, 'certificates/verify_error.html', context)
        
        context = {
            'certificate': certificate,
            'verified': True,
        }
        
        return render(request, 'certificates/verify_certificate.html', context)
        
    except Certificate.DoesNotExist:
        context = {
            'error': 'Certificat non trouvé. Veuillez vérifier le lien.',
        }
        return render(request, 'certificates/verify_error.html', context)


def shared_certificate(request, token):
    """Vue publique d'un certificat partagé"""
    try:
        share = get_object_or_404(
            CertificateShare.objects.select_related('certificate__course', 'certificate__user'),
            share_token=token,
            is_active=True
        )
        
        if share.is_expired():
            raise Http404("Ce lien de partage a expiré.")
        
        # Incrémenter le compteur de vues
        share.increment_view_count()
        
        certificate = share.certificate
        
        if not certificate.is_valid():
            context = {
                'error': 'Ce certificat n\'est plus valide.',
                'certificate': certificate
            }
            return render(request, 'certificates/verify_error.html', context)
        
        context = {
            'certificate': certificate,
            'shared': True,
        }
        
        return render(request, 'certificates/shared_certificate.html', context)
        
    except CertificateShare.DoesNotExist:
        raise Http404("Lien de partage non trouvé ou inactif.")


@login_required
@cache_control(max_age=3600)
def download_certificate(request, certificate_id, format='png'):
    """Téléchargement d'un certificat"""
    certificate = get_object_or_404(
        Certificate,
        id=certificate_id,
        user=request.user,
        status__in=['generated', 'issued']
    )
    
    if format == 'pdf' and certificate.pdf_file:
        response = HttpResponse(
            certificate.pdf_file.read(),
            content_type='application/pdf'
        )
        response['Content-Disposition'] = f'attachment; filename="certificat_{certificate.certificate_number}.pdf"'
        
    elif format == 'png' and certificate.certificate_file:
        response = HttpResponse(
            certificate.certificate_file.read(),
            content_type='image/png'
        )
        response['Content-Disposition'] = f'attachment; filename="certificat_{certificate.certificate_number}.png"'
        
    else:
        messages.error(request, "Format de fichier non disponible.")
        return redirect('certificates:certificate_detail', certificate_id=certificate_id)
    
    return response


@login_required
@require_http_methods(["POST"])
def regenerate_certificate(request, certificate_id):
    """Régénération d'un certificat"""
    certificate = get_object_or_404(
        Certificate.objects.select_related('enrollment'),
        id=certificate_id,
        user=request.user
    )
    
    try:
        with transaction.atomic():
            # Marquer l'ancien certificat comme révoqué
            certificate.revoke("Régénéré par l'utilisateur")
            
            # Créer un nouveau certificat
            new_certificate = certificate_generator.generate_certificate_for_enrollment(
                certificate.enrollment
            )
            
            if new_certificate:
                messages.success(request, "Certificat régénéré avec succès!")
                return redirect('certificates:certificate_detail', certificate_id=new_certificate.id)
            else:
                messages.error(request, "Erreur lors de la régénération du certificat.")
                
    except Exception as e:
        logger.error(f"Erreur lors de la régénération: {e}")
        messages.error(request, "Une erreur est survenue lors de la régénération.")
    
    return redirect('certificates:certificate_detail', certificate_id=certificate_id)


@staff_member_required
def admin_certificates_list(request):
    """Vue d'administration des certificats"""
    from django.db import models
    
    certificates = Certificate.objects.select_related(
        'user', 'course', 'template'
    ).order_by('-created_at')
    
    # Filtrage
    status = request.GET.get('status')
    if status:
        certificates = certificates.filter(status=status)
    
    search = request.GET.get('search')
    if search:
        certificates = certificates.filter(
            models.Q(certificate_number__icontains=search) |
            models.Q(user__username__icontains=search) |
            models.Q(course__title__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(certificates, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistiques
    stats = {
        'total': Certificate.objects.count(),
        'generated': Certificate.objects.filter(status='generated').count(),
        'issued': Certificate.objects.filter(status='issued').count(),
        'revoked': Certificate.objects.filter(status='revoked').count(),
    }
    
    context = {
        'page_obj': page_obj,
        'certificates': page_obj,
        'stats': stats,
        'status_choices': Certificate.STATUS_CHOICES,
        'current_status': status,
        'current_search': search,
    }
    
    return render(request, 'certificates/admin_certificates_list.html', context)


@staff_member_required
def admin_certificate_detail(request, certificate_id):
    """Vue d'administration d'un certificat spécifique"""
    certificate = get_object_or_404(
        Certificate.objects.select_related('user', 'course', 'template', 'enrollment'),
        id=certificate_id
    )
    
    context = {
        'certificate': certificate,
    }
    
    return render(request, 'certificates/admin_certificate_detail.html', context)


@staff_member_required
@require_http_methods(["POST"])
def admin_revoke_certificate(request, certificate_id):
    """Révocation d'un certificat par un administrateur"""
    certificate = get_object_or_404(Certificate, id=certificate_id)
    reason = request.POST.get('reason', 'Révoqué par un administrateur')
    
    certificate.revoke(reason)
    messages.success(request, f"Certificat {certificate.certificate_number} révoqué.")
    
    return redirect('certificates:admin_certificate_detail', certificate_id=certificate_id)


@staff_member_required
def templates_list(request):
    """Liste des templates de certificats"""
    templates = CertificateTemplate.objects.filter(is_active=True).order_by('-is_default', 'name')
    
    context = {
        'templates': templates,
    }
    
    return render(request, 'certificates/templates_list.html', context)


@login_required
def api_certificate_status(request, certificate_id):
    """API pour vérifier le statut d'un certificat"""
    try:
        certificate = Certificate.objects.get(
            id=certificate_id,
            user=request.user
        )
        
        data = {
            'status': certificate.status,
            'is_valid': certificate.is_valid(),
            'certificate_number': certificate.certificate_number,
            'generated_at': certificate.generated_at.isoformat() if certificate.generated_at else None,
        }
        
        return JsonResponse(data)
        
    except Certificate.DoesNotExist:
        return JsonResponse({'error': 'Certificat non trouvé'}, status=404)


@login_required
def certificate_statistics(request):
    """Statistiques des certificats de l'utilisateur"""
    user_certificates = Certificate.objects.filter(user=request.user)
    
    stats = {
        'total_certificates': user_certificates.count(),
        'certificates_by_month': {},
        'certificates_by_course': {},
        'average_grade': 0,
    }
    
    # Certificats par mois (12 derniers mois)
    from django.db.models import Count
    from django.db.models.functions import TruncMonth
    
    monthly_stats = user_certificates.filter(
        created_at__gte=timezone.now() - timezone.timedelta(days=365)
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')
    
    for stat in monthly_stats:
        month_key = stat['month'].strftime('%Y-%m')
        stats['certificates_by_month'][month_key] = stat['count']
    
    # Note moyenne
    certificates_with_grades = user_certificates.exclude(final_grade__isnull=True)
    if certificates_with_grades.exists():
        from django.db.models import Avg
        avg_grade = certificates_with_grades.aggregate(Avg('final_grade'))['final_grade__avg']
        stats['average_grade'] = round(float(avg_grade), 2) if avg_grade else 0
    
    return JsonResponse(stats)
