from django.urls import path
from . import views

app_name = 'certificates'

urlpatterns = [
    # Vues utilisateur
    path('', views.my_certificates, name='my_certificates'),
    path('<uuid:certificate_id>/', views.certificate_detail, name='certificate_detail'),
    path('<uuid:certificate_id>/download/<str:format>/', views.download_certificate, name='download_certificate'),
    path('<uuid:certificate_id>/regenerate/', views.regenerate_certificate, name='regenerate_certificate'),
    
    # API
    path('api/<uuid:certificate_id>/status/', views.api_certificate_status, name='api_certificate_status'),
    path('api/statistics/', views.certificate_statistics, name='api_certificate_statistics'),
    
    # Vérification et partage public
    path('verify/<str:hash>/', views.verify_certificate, name='verify'),
    path('share/<uuid:token>/', views.shared_certificate, name='shared_view'),
    
    # Administration
    path('admin/', views.admin_certificates_list, name='admin_certificates_list'),
    path('admin/<uuid:certificate_id>/', views.admin_certificate_detail, name='admin_certificate_detail'),
    path('admin/<uuid:certificate_id>/revoke/', views.admin_revoke_certificate, name='admin_revoke_certificate'),
    path('admin/templates/', views.templates_list, name='templates_list'),
]