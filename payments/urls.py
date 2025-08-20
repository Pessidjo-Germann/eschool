from django.urls import path
from . import views
from . import financial_views

app_name = 'payments'

urlpatterns = [
    # Vues principales de paiement
    path('initiate/', views.initiate_payment, name='initiate_payment'),
    path('course/<uuid:course_id>/summary/', views.course_order_summary, name='course_order_summary'),
    path('course/<uuid:course_id>/', views.course_payment, name='course_payment'),
    
    # Résultats de paiement
    path('success/<uuid:transaction_id>/', views.payment_success, name='payment_success'),
    path('cancelled/<uuid:transaction_id>/', views.payment_cancelled, name='payment_cancelled'),
    path('failure/<uuid:transaction_id>/', views.payment_failure, name='payment_failure'),
    
    # Gestion des transactions
    path('transaction/<uuid:transaction_id>/', views.transaction_detail, name='transaction_detail'),
    path('transactions/', views.user_transactions, name='user_transactions'),
    
    # API endpoints
    path('api/status/<uuid:transaction_id>/', views.check_transaction_status, name='check_status'),
    path('webhook/', views.webhook_endpoint, name='webhook'),
    
    # Administration
    path('admin/configuration/', views.PaymentConfigurationView.as_view(), name='configuration'),
    
    # Gestion financière
    path('financial/dashboard/', financial_views.financial_dashboard, name='financial_dashboard'),
    path('financial/reports/', financial_views.financial_reports, name='financial_reports'),
    path('export/transactions-csv/', financial_views.export_transactions_csv, name='export_transactions_csv'),
    path('export/accounting-data/', financial_views.export_accounting_data, name='export_accounting_data'),
    path('invoices/<int:invoice_id>/pdf/', financial_views.download_invoice_pdf, name='download_invoice_pdf'),
    path('invoices/<int:invoice_id>/send-email/', financial_views.send_invoice_email_view, name='send_invoice_email'),
    path('api/financial-data/', financial_views.api_financial_data, name='api_financial_data'),
]