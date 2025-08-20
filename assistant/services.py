"""
Services pour l'assistant virtuel avec intégration Gemini API
"""
import requests
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from django.conf import settings
from django.db.models import Q
from .models import (
    Conversation, Message, KnowledgeBase, 
    AssistantConfiguration, UserPreferences
)

logger = logging.getLogger(__name__)


class GeminiAPIError(Exception):
    """Exception personnalisée pour les erreurs API Gemini"""
    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class GeminiService:
    """Service pour l'intégration avec l'API Gemini de Google"""
    
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    
    def __init__(self, config: AssistantConfiguration = None):
        """Initialise le service avec une configuration"""
        if config is None:
            config = AssistantConfiguration.get_active_config()
            
        if not config:
            raise ValueError("Aucune configuration d'assistant active trouvée")
            
        self.config = config
        self.api_key = config.api_key
        
        # Headers pour les requêtes
        self.headers = {
            'Content-Type': 'application/json'
        }
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Dict = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Effectue une requête HTTP vers l'API Gemini"""
        try:
            url = f"{self.BASE_URL}/{endpoint}?key={self.api_key}"
            
            logger.info(f"Gemini API Request: {method} {endpoint}")
            
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                timeout=30
            )
            
            response_data = {}
            try:
                response_data = response.json()
            except ValueError:
                response_data = {'raw_response': response.text}
            
            logger.info(f"Gemini API Response: {response.status_code}")
            
            if response.status_code == 200:
                return True, response_data
            else:
                error_message = response_data.get('error', {}).get('message', 'Erreur API inconnue')
                raise GeminiAPIError(
                    message=error_message,
                    status_code=response.status_code
                )
                
        except requests.exceptions.Timeout:
            raise GeminiAPIError("Timeout lors de la requête API")
        except requests.exceptions.ConnectionError:
            raise GeminiAPIError("Erreur de connexion à l'API Gemini")
        except Exception as e:
            logger.error(f"Erreur lors de la requête Gemini: {e}")
            raise GeminiAPIError(f"Erreur inattendue: {str(e)}")
    
    def generate_content(
        self, 
        messages: List[Dict[str, str]], 
        system_prompt: str = None
    ) -> Tuple[bool, str, Dict]:
        """Génère une réponse avec Gemini"""
        try:
            # Préparer les messages pour Gemini
            contents = []
            
            # Ajouter le prompt système si fourni
            if system_prompt:
                contents.append({
                    "role": "user",
                    "parts": [{"text": f"INSTRUCTIONS: {system_prompt}"}]
                })
                contents.append({
                    "role": "model", 
                    "parts": [{"text": "Compris, je vais suivre ces instructions."}]
                })
            
            # Convertir les messages au format Gemini
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}]
                })
            
            # Préparer la requête
            request_data = {
                "contents": contents,
                "generationConfig": {
                    "temperature": self.config.temperature,
                    "maxOutputTokens": self.config.max_tokens,
                    "topP": 0.8,
                    "topK": 10
                }
            }
            
            # Effectuer la requête
            success, response_data = self._make_request(
                method='POST',
                endpoint=f'models/{self.config.model}:generateContent',
                data=request_data
            )
            
            if success:
                # Extraire la réponse
                candidates = response_data.get('candidates', [])
                if candidates:
                    content = candidates[0].get('content', {})
                    parts = content.get('parts', [])
                    if parts:
                        response_text = parts[0].get('text', '')
                        
                        # Métadonnées de réponse
                        metadata = {
                            'model': self.config.model,
                            'tokens_used': response_data.get('usageMetadata', {}),
                            'finish_reason': candidates[0].get('finishReason', ''),
                            'safety_ratings': candidates[0].get('safetyRatings', [])
                        }
                        
                        return True, response_text, metadata
            
            return False, "Aucune réponse générée", {}
            
        except GeminiAPIError:
            raise
        except Exception as e:
            logger.error(f"Erreur lors de la génération de contenu: {e}")
            raise GeminiAPIError(f"Erreur lors de la génération: {str(e)}")


class KnowledgeBaseService:
    """Service pour gérer la base de connaissances"""
    
    def search_knowledge(
        self, 
        query: str, 
        category: str = None, 
        limit: int = 5
    ) -> List[KnowledgeBase]:
        """Recherche dans la base de connaissances"""
        
        # Commencer par les entrées actives
        queryset = KnowledgeBase.objects.filter(is_active=True)
        
        # Filtrer par catégorie si spécifiée
        if category:
            queryset = queryset.filter(category=category)
        
        # Recherche par mots-clés et contenu
        search_terms = query.lower().split()
        q_objects = Q()
        
        for term in search_terms:
            q_objects |= (
                Q(question__icontains=term) |
                Q(answer__icontains=term) |
                Q(keywords__icontains=term) |
                Q(title__icontains=term)
            )
        
        results = queryset.filter(q_objects).order_by('-priority', '-usage_count')[:limit]
        
        # Marquer comme utilisées
        for entry in results:
            entry.increment_usage()
        
        return list(results)
    
    def get_relevant_context(
        self, 
        user_message: str, 
        conversation: Conversation = None
    ) -> str:
        """Obtient le contexte pertinent de la base de connaissances"""
        
        # Déterminer la catégorie probable
        category = self._detect_category(user_message)
        
        # Rechercher les entrées pertinentes
        relevant_entries = self.search_knowledge(
            query=user_message,
            category=category,
            limit=3
        )
        
        if not relevant_entries:
            return ""
        
        # Formater le contexte
        context_parts = ["CONTEXTE DE LA BASE DE CONNAISSANCES:"]
        
        for entry in relevant_entries:
            context_parts.append(f"\nQ: {entry.question}")
            context_parts.append(f"R: {entry.answer}")
        
        context_parts.append("\nUtilise ces informations pour enrichir ta réponse si pertinent.")
        
        return "\n".join(context_parts)
    
    def _detect_category(self, message: str) -> Optional[str]:
        """Détecte la catégorie probable d'un message"""
        message_lower = message.lower()
        
        # Mapping de mots-clés vers catégories
        category_keywords = {
            'payments': ['paiement', 'payer', 'prix', 'facture', 'coût', 'argent', 'mobile money', 'orange money', 'mtn'],
            'courses': ['cours', 'leçon', 'module', 'formation', 'apprentissage', 'étudier', 'apprendre'],
            'enrollment': ['inscription', 'inscrire', 'rejoindre', 's\'inscrire'],
            'account': ['compte', 'profil', 'mot de passe', 'connexion', 'déconnexion', 'email'],
            'technical': ['problème', 'erreur', 'bug', 'ne marche pas', 'dysfonction', 'aide technique'],
            'certificates': ['certificat', 'diplôme', 'badge', 'récompense', 'validation']
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                return category
        
        return None


class ConversationService:
    """Service pour gérer les conversations et le contexte"""
    
    def __init__(self):
        self.gemini_service = GeminiService()
        self.knowledge_service = KnowledgeBaseService()
    
    def get_or_create_conversation(
        self, 
        user=None, 
        session_id: str = None
    ) -> Conversation:
        """Obtient ou crée une conversation"""
        
        if user:
            # Pour les utilisateurs connectés, chercher une conversation active récente
            conversation = Conversation.objects.filter(
                user=user,
                is_active=True
            ).first()
            
            if not conversation:
                conversation = Conversation.objects.create(
                    user=user,
                    session_id=session_id or f"user_{user.id}"
                )
        else:
            # Pour les utilisateurs anonymes
            if not session_id:
                raise ValueError("session_id requis pour les utilisateurs anonymes")
                
            conversation = Conversation.objects.filter(
                session_id=session_id,
                is_active=True
            ).first()
            
            if not conversation:
                conversation = Conversation.objects.create(
                    session_id=session_id
                )
        
        return conversation
    
    def add_message(
        self, 
        conversation: Conversation, 
        role: str, 
        content: str, 
        metadata: Dict = None
    ) -> Message:
        """Ajoute un message à la conversation"""
        
        message = Message.objects.create(
            conversation=conversation,
            role=role,
            content=content,
            metadata=metadata or {}
        )
        
        # Générer un titre pour la conversation si nécessaire
        if not conversation.title and role == 'user':
            title = self._generate_conversation_title(content)
            conversation.title = title
            conversation.save(update_fields=['title'])
        
        # Mettre à jour le timestamp de la conversation
        conversation.save(update_fields=['updated_at'])
        
        return message
    
    def get_context_messages(
        self, 
        conversation: Conversation, 
        max_messages: int = None
    ) -> List[Dict[str, str]]:
        """Récupère les messages de contexte pour l'IA"""
        
        config = AssistantConfiguration.get_active_config()
        if not config:
            max_messages = 10
        else:
            max_messages = max_messages or config.max_context_messages
        
        # Récupérer les derniers messages (exclure les messages système)
        messages = conversation.messages.filter(
            role__in=['user', 'assistant']
        ).order_by('-timestamp')[:max_messages]
        
        # Inverser pour avoir l'ordre chronologique
        messages = list(reversed(messages))
        
        return [
            {
                'role': msg.role,
                'content': msg.content
            }
            for msg in messages
        ]
    
    def generate_response(
        self, 
        conversation: Conversation, 
        user_message: str,
        context_data: Dict = None
    ) -> Tuple[str, Dict]:
        """Génère une réponse de l'assistant"""
        
        try:
            # Ajouter le message de l'utilisateur
            self.add_message(conversation, 'user', user_message)
            
            # Obtenir la configuration
            config = AssistantConfiguration.get_active_config()
            if not config:
                return "Je ne suis pas configuré correctement. Contactez l'administrateur.", {}
            
            # Construire le prompt système
            system_prompt = config.system_prompt
            
            # Ajouter le contexte de la base de connaissances si activé
            if config.enable_knowledge_base:
                kb_context = self.knowledge_service.get_relevant_context(
                    user_message, conversation
                )
                if kb_context:
                    system_prompt += f"\n\n{kb_context}"
            
            # Ajouter le contexte utilisateur si fourni
            if context_data:
                context_info = []
                if context_data.get('current_course'):
                    context_info.append(f"Cours actuel: {context_data['current_course']}")
                if context_data.get('user_level'):
                    context_info.append(f"Niveau utilisateur: {context_data['user_level']}")
                
                if context_info:
                    system_prompt += f"\n\nCONTEXTE UTILISATEUR: {' | '.join(context_info)}"
            
            # Récupérer l'historique de conversation si activé
            messages = []
            if config.enable_context_memory:
                messages = self.get_context_messages(conversation)
            else:
                # Juste le dernier message
                messages = [{'role': 'user', 'content': user_message}]
            
            # Générer la réponse avec Gemini
            success, response_text, metadata = self.gemini_service.generate_content(
                messages=messages,
                system_prompt=system_prompt
            )
            
            if success:
                # Ajouter la réponse de l'assistant
                self.add_message(conversation, 'assistant', response_text, metadata)
                return response_text, metadata
            else:
                error_msg = "Désolé, je ne peux pas générer de réponse pour le moment."
                self.add_message(conversation, 'assistant', error_msg)
                return error_msg, {}
                
        except Exception as e:
            logger.error(f"Erreur lors de la génération de réponse: {e}")
            error_msg = "Une erreur s'est produite. Veuillez réessayer."
            return error_msg, {}
    
    def _generate_conversation_title(self, first_message: str) -> str:
        """Génère un titre pour la conversation basé sur le premier message"""
        
        # Prendre les premiers mots significatifs
        words = first_message.strip().split()
        
        # Supprimer les mots vides courants
        stop_words = {'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'ou', 'à', 'dans', 'sur', 'avec', 'par', 'pour'}
        meaningful_words = [w for w in words if w.lower() not in stop_words]
        
        # Prendre jusqu'à 4 mots significatifs
        title_words = meaningful_words[:4] if meaningful_words else words[:4]
        title = ' '.join(title_words)
        
        # Limiter la longueur
        if len(title) > 50:
            title = title[:47] + "..."
        
        return title.capitalize()


# Service principal exporté
def get_conversation_service() -> ConversationService:
    """Factory pour obtenir une instance du service de conversation"""
    return ConversationService()