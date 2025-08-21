from django.urls import path
from . import views

app_name = 'superadmin'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('users/', views.user_management, name='user_management'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('moderation/', views.content_moderation, name='content_moderation'),
    path('moderation/<str:content_type>/<int:content_id>/', views.moderate_content, name='moderate_content'),
    path('statistics/', views.platform_statistics, name='platform_statistics'),
    path('disputes/', views.payment_disputes, name='payment_disputes'),
    path('disputes/<int:dispute_id>/', views.dispute_detail, name='dispute_detail'),
    path('config/', views.system_configuration, name='system_configuration'),
    path('api/statistics/', views.api_statistics, name='api_statistics'),
]