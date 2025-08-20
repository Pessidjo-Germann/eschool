from django.urls import path
from . import views

app_name = 'assistant'

urlpatterns = [
    # Interface principale du chat
    path('', views.assistant_chat, name='chat'),
    
    # API endpoints
    path('api/message/', views.api_chat_message, name='api_chat_message'),
    
    # Base de connaissances publique (FAQ)
    path('faq/', views.knowledge_base_public, name='faq'),
]