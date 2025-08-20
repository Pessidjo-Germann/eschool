from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
import json
import uuid
import logging

from .models import Conversation, Message, KnowledgeBase, AssistantConfiguration
from .services import get_conversation_service, GeminiAPIError

logger = logging.getLogger(__name__)


def assistant_chat(request):
    """Page principale de l'assistant de chat"""
    
    # Récupérer les catégories de la base de connaissances pour suggestions
    categories = KnowledgeBase.objects.filter(is_active=True).values_list('category', flat=True).distinct()
    
    # Récupérer quelques questions populaires
    popular_questions = KnowledgeBase.objects.filter(
        is_active=True, 
        usage_count__gt=0
    ).order_by('-usage_count')[:5]
    
    context = {
        'categories': categories,
        'popular_questions': popular_questions,
    }
    
    # Si l'utilisateur est connecté, récupérer ses conversations récentes
    if request.user.is_authenticated:
        recent_conversations = Conversation.objects.filter(
            user=request.user,
            is_active=True
        ).order_by('-updated_at')[:5]
        context['recent_conversations'] = recent_conversations
    
    return render(request, 'assistant/chat.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def api_chat_message(request):
    """API endpoint pour envoyer un message à l'assistant"""
    
    try:
        data = json.loads(request.body)
        message_content = data.get('message', '').strip()
        conversation_id = data.get('conversation_id')
        session_id = data.get('session_id')
        
        if not message_content:
            return JsonResponse({
                'error': 'Message requis'
            }, status=400)
        
        # Obtenir le service de conversation
        conversation_service = get_conversation_service()
        
        # Obtenir ou créer la conversation
        if conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id)
                # Vérifier les permissions
                if request.user.is_authenticated:
                    if conversation.user and conversation.user != request.user:
                        return JsonResponse({'error': 'Non autorisé'}, status=403)
                else:
                    if not session_id or conversation.session_id != session_id:
                        return JsonResponse({'error': 'Session invalide'}, status=403)
            except Conversation.DoesNotExist:
                return JsonResponse({'error': 'Conversation introuvable'}, status=404)
        else:
            # Créer une nouvelle conversation
            user = request.user if request.user.is_authenticated else None
            if not user and not session_id:
                session_id = str(uuid.uuid4())
            
            conversation = conversation_service.get_or_create_conversation(
                user=user,
                session_id=session_id
            )
        
        # Préparer le contexte utilisateur
        context_data = {}
        if request.user.is_authenticated:
            context_data['user_level'] = 'authenticated'
        
        # Générer la réponse
        response_text, metadata = conversation_service.generate_response(
            conversation=conversation,
            user_message=message_content,
            context_data=context_data
        )
        
        return JsonResponse({
            'success': True,
            'response': response_text,
            'conversation_id': str(conversation.id),
            'session_id': conversation.session_id,
            'metadata': {
                'message_count': conversation.messages.count(),
                'conversation_title': conversation.title,
                'tokens_used': metadata.get('tokens_used', {}),
                'model': metadata.get('model', '')
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalide'}, status=400)
    except GeminiAPIError as e:
        logger.error(f"Erreur API Gemini: {e}")
        return JsonResponse({
            'error': 'Service temporairement indisponible. Veuillez réessayer.',
            'details': str(e) if hasattr(e, 'message') else str(e)
        }, status=503)
    except Exception as e:
        logger.error(f"Erreur dans api_chat_message: {e}")
        return JsonResponse({
            'error': 'Erreur interne du serveur'
        }, status=500)


def knowledge_base_public(request):
    """Page publique de la base de connaissances (FAQ)"""
    
    category_filter = request.GET.get('category', '')
    search_query = request.GET.get('q', '')
    
    # Récupérer les entrées de la base de connaissances
    entries = KnowledgeBase.objects.filter(is_active=True)
    
    # Filtrage par catégorie
    if category_filter:
        entries = entries.filter(category=category_filter)
    
    # Recherche textuelle
    if search_query:
        from django.db.models import Q
        search_terms = search_query.lower().split()
        q_objects = Q()
        for term in search_terms:
            q_objects |= (
                Q(question__icontains=term) |
                Q(answer__icontains=term) |
                Q(keywords__icontains=term) |
                Q(title__icontains=term)
            )
        entries = entries.filter(q_objects)
    
    entries = entries.order_by('-priority', '-usage_count')
    
    # Récupérer les catégories pour le filtre
    categories = KnowledgeBase.objects.filter(is_active=True).values_list('category', flat=True).distinct()
    
    context = {
        'entries': entries,
        'categories': categories,
        'current_category': category_filter,
        'search_query': search_query,
    }
    
    return render(request, 'assistant/knowledge_base.html', context)
