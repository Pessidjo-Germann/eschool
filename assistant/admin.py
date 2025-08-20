from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Conversation, Message, KnowledgeBase, 
    AssistantConfiguration, UserPreferences
)


@admin.register(AssistantConfiguration)
class AssistantConfigurationAdmin(admin.ModelAdmin):
    list_display = ['name', 'model', 'is_active', 'created_at']
    list_filter = ['model', 'is_active', 'created_at']
    search_fields = ['name']
    
    fieldsets = (
        ('Configuration de base', {
            'fields': ('name', 'is_active')
        }),
        ('API Gemini', {
            'fields': ('api_key', 'model')
        }),
        ('Paramètres de génération', {
            'fields': ('max_tokens', 'temperature')
        }),
        ('Personnalisation', {
            'fields': ('system_prompt',)
        }),
        ('Fonctionnalités', {
            'fields': (
                'enable_knowledge_base', 
                'enable_context_memory', 
                'max_context_messages'
            )
        }),
    )
    
    def has_delete_permission(self, request, obj=None):
        # Empêcher la suppression si c'est la seule config active
        if obj and obj.is_active:
            active_count = AssistantConfiguration.objects.filter(is_active=True).count()
            return active_count > 1
        return True


@admin.register(KnowledgeBase)
class KnowledgeBaseAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'is_active', 'priority', 'usage_count', 'last_used']
    list_filter = ['category', 'is_active', 'created_at', 'priority']
    search_fields = ['title', 'question', 'answer', 'keywords']
    ordering = ['-priority', '-updated_at']
    
    fieldsets = (
        ('Information principale', {
            'fields': ('title', 'category', 'question', 'answer')
        }),
        ('Recherche', {
            'fields': ('keywords',)
        }),
        ('Gestion', {
            'fields': ('is_active', 'priority')
        }),
        ('Statistiques', {
            'fields': ('usage_count', 'last_used'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['usage_count', 'last_used', 'created_at', 'updated_at']
    
    def save_model(self, request, obj, form, change):
        if not change:  # Nouveau object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ['timestamp', 'metadata']
    fields = ['role', 'content', 'timestamp', 'is_helpful']
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user_info', 'messages_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at', 'updated_at']
    search_fields = ['title', 'user__username', 'session_id']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [MessageInline]
    
    def user_info(self, obj):
        if obj.user:
            return f"{obj.user.username}"
        return f"Session: {obj.session_id[:8]}..."
    user_info.short_description = "Utilisateur"
    
    def messages_count(self, obj):
        return obj.messages.count()
    messages_count.short_description = "Messages"
    
    fieldsets = (
        ('Information', {
            'fields': ('title', 'user', 'session_id', 'is_active')
        }),
        ('Contexte', {
            'fields': ('context_data',),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['conversation_title', 'role', 'content_preview', 'timestamp', 'is_helpful']
    list_filter = ['role', 'timestamp', 'is_helpful']
    search_fields = ['content', 'conversation__title']
    readonly_fields = ['timestamp', 'metadata']
    
    def conversation_title(self, obj):
        return obj.conversation.title or f"Conv. {str(obj.conversation.id)[:8]}"
    conversation_title.short_description = "Conversation"
    
    def content_preview(self, obj):
        preview = obj.content[:100]
        if len(obj.content) > 100:
            preview += "..."
        return preview
    content_preview.short_description = "Contenu"
    
    fieldsets = (
        ('Message', {
            'fields': ('conversation', 'role', 'content')
        }),
        ('Feedback', {
            'fields': ('is_helpful',)
        }),
        ('Métadonnées', {
            'fields': ('metadata', 'timestamp'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ['user', 'preferred_language', 'response_style', 'save_conversation_history']
    list_filter = ['preferred_language', 'response_style', 'save_conversation_history']
    search_fields = ['user__username', 'user__email']
    
    fieldsets = (
        ('Utilisateur', {
            'fields': ('user',)
        }),
        ('Préférences de communication', {
            'fields': ('preferred_language', 'response_style')
        }),
        ('Notifications', {
            'fields': ('enable_suggestions', 'enable_course_recommendations')
        }),
        ('Historique', {
            'fields': ('save_conversation_history',)
        }),
    )
