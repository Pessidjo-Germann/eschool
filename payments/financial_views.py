"""
Vues pour la gestion financière : exports comptables, tableau de bord, etc.
"""
import csv
import json
from datetime import datetime, date, timedelta
from decimal import Decimal
from io import BytesIO, StringIO

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Avg, Q, F
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib import messages

from .models import PaymentTransaction, Invoice
from .invoice_services import invoice_generator, invoice_email_service
import logging

logger = logging.getLogger(__name__)


@staff_member_required
def financial_dashboard(request):
    """Tableau de bord financier avec graphiques et statistiques"""
    
    # Période par défaut (30 derniers jours)
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    # Récupérer les paramètres de filtre
    if request.GET.get('start_date'):
        start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d').date()
    if request.GET.get('end_date'):
        end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d').date()
    
    period = request.GET.get('period', 'month')  # day, week, month
    
    # Statistiques générales
    stats = _get_financial_stats(start_date, end_date)
    
    # Données pour les graphiques
    revenue_data = _get_revenue_chart_data(start_date, end_date, period)
    transaction_data = _get_transaction_chart_data(start_date, end_date, period)
    method_data = _get_payment_method_data(start_date, end_date)
    
    # Transactions récentes
    recent_transactions = PaymentTransaction.objects.filter(
        created_at__date__range=[start_date, end_date],
        status='completed'
    ).select_related('user').order_by('-created_at')[:10]
    
    # Factures en retard
    overdue_invoices = Invoice.objects.filter(
        due_date__lt=timezone.now().date(),
        status__in=['draft', 'sent']
    ).select_related('user').order_by('due_date')[:5]
    
    context = {
        'stats': stats,
        'revenue_data': json.dumps(revenue_data),
        'transaction_data': json.dumps(transaction_data),
        'method_data': json.dumps(method_data),
        'recent_transactions': recent_transactions,
        'overdue_invoices': overdue_invoices,
        'start_date': start_date,
        'end_date': end_date,
        'period': period,
    }
    
    return render(request, 'payments/financial_dashboard.html', context)


def _get_financial_stats(start_date, end_date):
    """Calculer les statistiques financières"""
    
    transactions = PaymentTransaction.objects.filter(
        created_at__date__range=[start_date, end_date]
    )
    
    stats = {
        'total_revenue': transactions.filter(status='completed').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0'),
        
        'total_transactions': transactions.count(),
        
        'successful_transactions': transactions.filter(status='completed').count(),
        
        'average_transaction': transactions.filter(status='completed').aggregate(
            avg=Avg('amount')
        )['avg'] or Decimal('0'),
        
        'pending_amount': transactions.filter(status='pending').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0'),
        
        'failed_transactions': transactions.filter(status='failed').count(),
        
        'success_rate': 0,
    }
    
    # Calculer le taux de succès
    if stats['total_transactions'] > 0:
        stats['success_rate'] = (stats['successful_transactions'] / stats['total_transactions']) * 100
    
    # Comparaison avec la période précédente
    previous_start = start_date - (end_date - start_date)
    previous_end = start_date
    
    previous_revenue = PaymentTransaction.objects.filter(
        created_at__date__range=[previous_start, previous_end],
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    if previous_revenue > 0:
        revenue_change = ((stats['total_revenue'] - previous_revenue) / previous_revenue) * 100
    else:
        revenue_change = 100 if stats['total_revenue'] > 0 else 0
    
    stats['revenue_change'] = revenue_change
    
    return stats


def _get_revenue_chart_data(start_date, end_date, period):
    """Obtenir les données pour le graphique des revenus"""
    
    if period == 'day':
        trunc_func = TruncDate
        date_format = '%Y-%m-%d'
    elif period == 'week':
        trunc_func = TruncWeek
        date_format = '%Y-W%W'
    else:  # month
        trunc_func = TruncMonth
        date_format = '%Y-%m'
    
    data = PaymentTransaction.objects.filter(
        created_at__date__range=[start_date, end_date],
        status='completed'
    ).annotate(
        period=trunc_func('created_at')
    ).values('period').annotate(
        revenue=Sum('amount'),
        count=Count('id')
    ).order_by('period')
    
    # Formater pour Chart.js
    labels = []
    revenues = []
    counts = []
    
    for item in data:
        if period == 'day':
            label = item['period'].strftime('%d/%m')
        elif period == 'week':
            label = f"S{item['period'].strftime('%W')}"
        else:
            label = item['period'].strftime('%m/%Y')
        
        labels.append(label)
        revenues.append(float(item['revenue']))
        counts.append(item['count'])
    
    return {
        'labels': labels,
        'revenues': revenues,
        'counts': counts
    }


def _get_transaction_chart_data(start_date, end_date, period):
    """Obtenir les données pour le graphique des transactions par statut"""
    
    data = PaymentTransaction.objects.filter(
        created_at__date__range=[start_date, end_date]
    ).values('status').annotate(
        count=Count('id'),
        amount=Sum('amount')
    ).order_by('status')
    
    return {
        'labels': [item['status'].title() for item in data],
        'counts': [item['count'] for item in data],
        'amounts': [float(item['amount'] or 0) for item in data]
    }


def _get_payment_method_data(start_date, end_date):
    """Obtenir les données par méthode de paiement"""
    
    data = PaymentTransaction.objects.filter(
        created_at__date__range=[start_date, end_date],
        status='completed'
    ).values('payment_method').annotate(
        count=Count('id'),
        amount=Sum('amount')
    ).order_by('-amount')
    
    # Remplacer None par 'Non spécifié'
    for item in data:
        if not item['payment_method']:
            item['payment_method'] = 'Non spécifié'
    
    return {
        'labels': [item['payment_method'] for item in data],
        'counts': [item['count'] for item in data],
        'amounts': [float(item['amount']) for item in data]
    }


@staff_member_required
@require_http_methods(["GET"])
def export_transactions_csv(request):
    """Exporter les transactions en CSV"""
    
    # Paramètres de filtre
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    status = request.GET.get('status')
    payment_method = request.GET.get('payment_method')
    
    # Construction de la requête
    queryset = PaymentTransaction.objects.select_related('user').all()
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        queryset = queryset.filter(created_at__date__gte=start_date)
    
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        queryset = queryset.filter(created_at__date__lte=end_date)
    
    if status:
        queryset = queryset.filter(status=status)
    
    if payment_method:
        queryset = queryset.filter(payment_method=payment_method)
    
    queryset = queryset.order_by('-created_at')
    
    # Création du CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="transactions_export_{date.today()}.csv"'
    
    writer = csv.writer(response)
    
    # En-têtes
    writer.writerow([
        'Référence',
        'Utilisateur',
        'Email',
        'Montant',
        'Devise',
        'Statut',
        'Méthode de paiement',
        'Description',
        'Date de création',
        'Date de paiement',
        'Frais de traitement',
        'Montant net',
        'Code erreur',
        'Message erreur'
    ])
    
    # Données
    for transaction in queryset:
        writer.writerow([
            transaction.reference,
            transaction.user.get_full_name() if transaction.user else transaction.customer_name,
            transaction.customer_email,
            transaction.amount,
            transaction.currency,
            transaction.get_status_display(),
            transaction.get_payment_method_display() if transaction.payment_method else '',
            transaction.description,
            transaction.created_at.strftime('%d/%m/%Y %H:%M'),
            transaction.paid_at.strftime('%d/%m/%Y %H:%M') if transaction.paid_at else '',
            transaction.processing_fee or '',
            transaction.net_amount or '',
            transaction.error_code or '',
            transaction.error_message or ''
        ])
    
    logger.info(f"Export CSV généré avec {queryset.count()} transactions")
    return response


@staff_member_required
@require_http_methods(["GET"])
def export_accounting_data(request):
    """Exporter les données comptables (format FEC - Fichier des Écritures Comptables)"""
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date or not end_date:
        messages.error(request, "Les dates de début et fin sont obligatoires")
        return JsonResponse({'error': 'Dates manquantes'}, status=400)
    
    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Transactions complétées dans la période
    transactions = PaymentTransaction.objects.filter(
        paid_at__date__range=[start_date, end_date],
        status='completed'
    ).select_related('user').order_by('paid_at')
    
    # Création du fichier FEC
    response = HttpResponse(content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="FEC_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.txt"'
    
    # En-tête FEC (format normalisé)
    fec_lines = []
    
    for transaction in transactions:
        # Numéro de journal (VT = Ventes)
        journal_code = "VT"
        
        # Date de pièce
        piece_date = transaction.paid_at.strftime('%Y%m%d')
        
        # Numéro de pièce
        piece_num = f"VT{transaction.paid_at.strftime('%Y%m%d')}{transaction.id}"
        
        # Compte client (411 + code client)
        customer_account = f"411{transaction.user.id if transaction.user else '000'}"
        
        # Libellé
        label = f"Vente - {transaction.description[:30]}"
        
        # Écriture débit (compte client)
        fec_lines.append(f"{journal_code}|{piece_date}|{piece_num}|{customer_account}|{label}|{float(transaction.amount):.2f}|0.00|D|{piece_date}")
        
        # Écriture crédit (compte produit - 706 Prestations de services)
        product_account = "706000"
        fec_lines.append(f"{journal_code}|{piece_date}|{piece_num}|{product_account}|{label}|0.00|{float(transaction.amount):.2f}|C|{piece_date}")
        
        # Si frais de traitement
        if transaction.processing_fee and transaction.processing_fee > 0:
            fee_account = "627000"  # Compte frais bancaires
            fec_lines.append(f"{journal_code}|{piece_date}|{piece_num}|{fee_account}|Frais bancaires|{float(transaction.processing_fee):.2f}|0.00|D|{piece_date}")
    
    # Écrire toutes les lignes
    response.write('\n'.join(fec_lines))
    
    logger.info(f"Export comptable FEC généré pour {transactions.count()} transactions")
    return response


@login_required
def download_invoice_pdf(request, invoice_id):
    """Télécharger le PDF d'une facture"""
    
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    # Vérifier les permissions
    if not request.user.is_staff and invoice.user != request.user:
        raise Http404("Facture non trouvée")
    
    try:
        # Générer ou récupérer le PDF
        if invoice.pdf_file and invoice.pdf_file.name:
            # PDF existe déjà
            response = HttpResponse(invoice.pdf_file.read(), content_type='application/pdf')
        else:
            # Générer un nouveau PDF
            pdf_content = invoice_generator.generate_invoice_pdf(invoice)
            response = HttpResponse(pdf_content, content_type='application/pdf')
            
            # Optionnel : sauvegarder le PDF généré
            from django.core.files.base import ContentFile
            invoice.pdf_file.save(
                f"facture_{invoice.invoice_number}.pdf",
                ContentFile(pdf_content),
                save=True
            )
        
        response['Content-Disposition'] = f'attachment; filename="facture_{invoice.invoice_number}.pdf"'
        
        logger.info(f"PDF de facture téléchargé: {invoice.invoice_number}")
        return response
        
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement du PDF {invoice.invoice_number}: {e}")
        messages.error(request, "Erreur lors de la génération du PDF")
        return JsonResponse({'error': 'Erreur de génération PDF'}, status=500)


@login_required 
def send_invoice_email_view(request, invoice_id):
    """Envoyer une facture par email (vue AJAX)"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    # Vérifier les permissions
    if not request.user.is_staff and invoice.user != request.user:
        return JsonResponse({'error': 'Permission refusée'}, status=403)
    
    try:
        # Envoyer l'email
        success = invoice_email_service.send_invoice_email(invoice)
        
        if success:
            return JsonResponse({
                'success': True,
                'message': f'Facture {invoice.invoice_number} envoyée par email'
            })
        else:
            return JsonResponse({
                'error': 'Erreur lors de l\'envoi de l\'email'
            }, status=500)
            
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi email pour {invoice.invoice_number}: {e}")
        return JsonResponse({
            'error': 'Erreur inattendue lors de l\'envoi'
        }, status=500)


@staff_member_required
def financial_reports(request):
    """Page des rapports financiers"""
    
    # Statistiques des 12 derniers mois
    today = date.today()
    start_of_year = date(today.year, 1, 1)
    
    monthly_revenue = PaymentTransaction.objects.filter(
        paid_at__date__gte=start_of_year,
        status='completed'
    ).annotate(
        month=TruncMonth('paid_at')
    ).values('month').annotate(
        revenue=Sum('amount'),
        count=Count('id')
    ).order_by('month')
    
    # Top utilisateurs par revenus
    top_customers = PaymentTransaction.objects.filter(
        status='completed',
        paid_at__date__gte=today - timedelta(days=365)
    ).values(
        'user__first_name', 
        'user__last_name',
        'user__email'
    ).annotate(
        total_spent=Sum('amount'),
        transaction_count=Count('id')
    ).order_by('-total_spent')[:10]
    
    # Factures par statut
    invoice_stats = Invoice.objects.values('status').annotate(
        count=Count('id'),
        amount=Sum('total_amount')
    )
    
    context = {
        'monthly_revenue': monthly_revenue,
        'top_customers': top_customers,
        'invoice_stats': invoice_stats,
        'current_year': today.year,
    }
    
    return render(request, 'payments/financial_reports.html', context)


@staff_member_required
@require_http_methods(["GET"])
def api_financial_data(request):
    """API pour les données financières (AJAX)"""
    
    data_type = request.GET.get('type')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not all([data_type, start_date, end_date]):
        return JsonResponse({'error': 'Paramètres manquants'}, status=400)
    
    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        if data_type == 'revenue':
            data = _get_revenue_chart_data(start_date, end_date, 'day')
        elif data_type == 'transactions':
            data = _get_transaction_chart_data(start_date, end_date, 'day')
        elif data_type == 'methods':
            data = _get_payment_method_data(start_date, end_date)
        else:
            return JsonResponse({'error': 'Type de données non supporté'}, status=400)
        
        return JsonResponse(data)
        
    except ValueError:
        return JsonResponse({'error': 'Format de date invalide'}, status=400)
    except Exception as e:
        logger.error(f"Erreur API financial data: {e}")
        return JsonResponse({'error': 'Erreur serveur'}, status=500)