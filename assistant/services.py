"""
Services pour l'assistant virtuel avec intégration Gemini API
"""
import google.generativeai as genai
import json
import logging
import os
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
    
    def __init__(self, config: AssistantConfiguration = None):
        """Initialise le service avec une configuration"""
        if config is None:
            config = AssistantConfiguration.get_active_config()
            
        if not config:
            # Fallback vers les variables d'environnement
            from django.conf import settings
            api_key = getattr(settings, 'GEMINI_API_KEY', '')
            model_name = getattr(settings, 'GEMINI_MODEL', 'gemini-2.5-flash')
            
            if not api_key:
                raise ValueError("Aucune configuration d'assistant active trouvée et pas de clé API dans les variables d'environnement")
            
            # Créer une configuration temporaire
            class TempConfig:
                def __init__(self, api_key, model_name):
                    self.api_key = api_key
                    self.model = model_name  
                    self.max_tokens = 2048
                    self.temperature = 0.7
                    
            config = TempConfig(api_key, model_name)
            
        self.config = config
        self.api_key = "AIzaSyDfcxNav04S4SWpnYP3wXcWOeIDdCrg16Q"
        
        # Configurer la clé API pour genai
        genai.configure(api_key=self.api_key)
        
        # Initialiser le modèle
        self.model = genai.GenerativeModel(self.config.model)
    
    
    def generate_content(
        self, 
        messages: List[Dict[str, str]], 
        system_prompt: str = None
    ) -> Tuple[bool, str, Dict]:
        """Génère une réponse avec Gemini"""
        
        # Mode simulation si clé API fictive
        if 'YOUR_GEMINI_API_KEY_HERE' in self.api_key or not self.api_key.startswith('AI'):
            return self._simulate_response(messages, system_prompt)
        
        try:
            # Préparer le contenu pour l'API
            contents = []
            
            # Ajouter le prompt système si fourni
            if system_prompt:
                contents.append(f"INSTRUCTIONS: {system_prompt}")
            
            # Ajouter l'historique des messages
            for msg in messages:
                contents.append(msg["content"])
            
            # Prendre seulement le dernier message pour la génération
            current_message = messages[-1]["content"] if messages else ""
            if system_prompt:
                current_message = f"INSTRUCTIONS: {system_prompt}\n\n{current_message}"
            
            # Générer la réponse avec l'API google-generativeai
            response = self.model.generate_content(current_message)
            
            # Extraire le texte de la réponse
            response_text = response.text
            
            # Métadonnées de réponse
            metadata = {
                'model': self.config.model,
                'success': True
            }
            
            return True, response_text, metadata
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération avec Gemini Client: {e}")
            # Fallback vers le mode simulation en cas d'erreur
            return self._simulate_response(messages, system_prompt)
    
    def _simulate_response(
        self, 
        messages: List[Dict[str, str]], 
        system_prompt: str = None
    ) -> Tuple[bool, str, Dict]:
        """Simule une réponse Gemini pour les tests"""
        
        # Récupérer le dernier message de l'utilisateur
        user_message = ""
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                user_message = msg.get('content', '').lower()
                break
        
        # Réponses simulées basées sur des mots-clés
        if any(word in user_message for word in ['bonjour', 'salut', 'hello']):
            response = "Bonjour ! Je suis votre assistant virtuel. Comment puis-je vous aider aujourd'hui ?"
        
        elif any(word in user_message for word in ['cours', 'formation', 'apprendre']):
            response = """Nous proposons une large gamme de cours dans différents domaines :

🎯 **Développement web** - HTML, CSS, JavaScript, Python, Django
💼 **Marketing digital** - SEO, réseaux sociaux, publicité en ligne  
🎨 **Design** - Photoshop, Illustrator, UI/UX
📊 **Gestion** - Management, entrepreneuriat, finance

Tous nos cours incluent des vidéos, exercices pratiques et un certificat de réussite. Voulez-vous que je vous aide à choisir un cours ?"""

        elif any(word in user_message for word in ['paiement', 'payer', 'prix', 'coût']):
            response = """Pour les paiements, nous acceptons :

💳 **Mobile Money** - MTN Money, Orange Money (paiement instantané)
🏦 **Cartes bancaires** - Visa, Mastercard
💰 **Virements** - Express Union

**Sécurité** : Tous les paiements sont sécurisés avec chiffrement SSL 256-bit.
**Garantie** : Remboursement sous 30 jours si vous n'êtes pas satisfait.

Avez-vous une question spécifique sur les paiements ?"""

        elif any(word in user_message for word in ['inscription', 'inscrire', 'commencer']):
            response = """Pour vous inscrire à un cours :

1️⃣ **Créez votre compte** (gratuit)
2️⃣ **Parcourez les cours** disponibles
3️⃣ **Cliquez sur "S'inscrire"** sur le cours choisi
4️⃣ **Effectuez le paiement** 
5️⃣ **Commencez à apprendre** immédiatement !

Une fois inscrit, vous avez un accès à vie au contenu. Puis-je vous aider à choisir un cours ?"""

        elif any(word in user_message for word in ['problème', 'erreur', 'aide', 'support']):
            response = """Je peux vous aider avec les problèmes courants :

🔧 **Problèmes de connexion** - Vérifiez email/mot de passe
🎯 **Accès aux cours** - Vérifiez votre inscription
💳 **Problèmes de paiement** - Contactez votre banque
📱 **Problèmes techniques** - Essayez un autre navigateur

Pour une aide personnalisée, décrivez-moi votre problème précis et je vous guiderai étape par étape."""

        elif any(word in user_message for word in ['certificat', 'diplôme', 'badge']):
            response = """🏆 **Certificats de réussite** :

✅ **Comment l'obtenir** :
- Terminer tous les modules (100%)
- Réussir les quiz (70% minimum)
- Compléter le projet final si requis

📄 **Format** : PDF téléchargeable avec code de vérification unique
🏢 **Reconnaissance** : Accepté par de nombreuses entreprises
💼 **Utilisation** : Parfait pour valoriser votre CV !

Le certificat est généré automatiquement dès que vous remplissez tous les critères."""

        else:
            response = f"""Je comprends votre question. En tant qu'assistant virtuel de la plateforme e-learning, je peux vous aider avec :

🎓 **Les cours** - Choix, inscription, contenu
💳 **Les paiements** - Méthodes, sécurité, facturation  
👤 **Votre compte** - Création, gestion, préférences
🏆 **Les certificats** - Obtention, téléchargement
🔧 **Support technique** - Problèmes, bugs, aide

**Mode simulation actuel** - Pour utiliser l'IA complète, configurez une vraie clé API Gemini dans l'administration.

Pouvez-vous me dire plus précisément comment je peux vous aider ?"""
        
        # Métadonnées simulées
        metadata = {
            'model': 'simulation',
            'tokens_used': {'input_tokens': len(user_message), 'output_tokens': len(response)},
            'finish_reason': 'completed',
            'simulation': True
        }
        
        return True, response, metadata


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