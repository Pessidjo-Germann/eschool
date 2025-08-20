from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import (
    Category, Course, Tag, Module, Lesson, LessonResource,
    Enrollment, CourseFavorite, LessonCompletion, CourseReview,
    Currency, PricingTier, PricingModel, CourseBundle, 
    PromotionCode, PromotionCodeUsage, ModulePricing
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'courses_count', 'color_display', 'is_active', 'order')
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'description')
    ordering = ('order', 'name')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('name', 'slug', 'description', 'parent')
        }),
        ('Apparence', {
            'fields': ('icon', 'color', 'order')
        }),
        ('Paramètres', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def courses_count(self, obj):
        return obj.get_all_courses_count()
    courses_count.short_description = 'Nombre de cours'
    
    def color_display(self, obj):
        if obj.color:
            return format_html(
                '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
                obj.color, obj.color
            )
        return '-'
    color_display.short_description = 'Couleur'


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'color_display', 'courses_count', 'created_at')
    search_fields = ('name',)
    ordering = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at',)
    
    def courses_count(self, obj):
        return obj.courses.count()
    courses_count.short_description = 'Nombre de cours'
    
    def color_display(self, obj):
        if obj.color:
            return format_html(
                '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
                obj.color, obj.color
            )
        return '-'
    color_display.short_description = 'Couleur'


class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0
    fields = ('order', 'title', 'is_published', 'is_free', 'estimated_duration')
    readonly_fields = ('total_lessons',)
    ordering = ('order',)
    
    def total_lessons(self, obj):
        if obj.pk:
            return obj.total_lessons
        return 0
    total_lessons.short_description = 'Leçons'


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'instructor', 'category', 'status', 'difficulty', 
        'is_free', 'price', 'modules_count', 'lessons_count', 
        'enrollment_count', 'is_featured', 'created_at'
    )
    list_filter = (
        'status', 'difficulty', 'language', 'is_free', 'is_featured',
        'has_certificate', 'category', 'created_at'
    )
    search_fields = ('title', 'description', 'instructor__username', 'instructor__first_name', 'instructor__last_name')
    ordering = ('-created_at',)
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ('tags', 'co_instructors')
    readonly_fields = (
        'id', 'view_count', 'enrollment_count', 'modules_count', 
        'lessons_count', 'total_duration_display', 'created_at', 'updated_at'
    )
    inlines = [ModuleInline]
    
    fieldsets = (
        ('Informations de base', {
            'fields': (
                'title', 'slug', 'description', 'short_description',
                'category', 'tags'
            )
        }),
        ('Médias', {
            'fields': ('thumbnail', 'video_intro'),
            'classes': ('collapse',)
        }),
        ('Instructeurs', {
            'fields': ('instructor', 'co_instructors')
        }),
        ('Paramètres du cours', {
            'fields': (
                'difficulty', 'language', 'estimated_duration',
                'max_students', 'prerequisites', 'learning_objectives',
                'target_audience'
            )
        }),
        ('Prix et monétisation', {
            'fields': ('is_free', 'price', 'currency')
        }),
        ('Publication', {
            'fields': ('status', 'is_featured', 'publish_date')
        }),
        ('Certificat', {
            'fields': ('has_certificate', 'certificate_template'),
            'classes': ('collapse',)
        }),
        ('SEO', {
            'fields': ('meta_description', 'meta_keywords'),
            'classes': ('collapse',)
        }),
        ('Statistiques', {
            'fields': (
                'view_count', 'enrollment_count', 'modules_count',
                'lessons_count', 'total_duration_display'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def modules_count(self, obj):
        return obj.total_modules
    modules_count.short_description = 'Modules'
    
    def lessons_count(self, obj):
        return obj.total_lessons
    lessons_count.short_description = 'Leçons'
    
    def total_duration_display(self, obj):
        duration = obj.total_duration
        if duration > 0:
            hours = int(duration)
            minutes = int((duration - hours) * 60)
            return f"{hours}h {minutes}min"
        return "Non calculée"
    total_duration_display.short_description = 'Durée totale'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'instructor', 'category'
        ).prefetch_related('tags', 'co_instructors')
    
    actions = ['publish_courses', 'unpublish_courses', 'feature_courses', 'unfeature_courses']
    
    def publish_courses(self, request, queryset):
        updated = queryset.update(status='published', publish_date=timezone.now())
        self.message_user(request, f'{updated} cours ont été publiés.')
    publish_courses.short_description = 'Publier les cours sélectionnés'
    
    def unpublish_courses(self, request, queryset):
        updated = queryset.update(status='draft')
        self.message_user(request, f'{updated} cours ont été dépubliés.')
    unpublish_courses.short_description = 'Dépublier les cours sélectionnés'
    
    def feature_courses(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} cours ont été mis en avant.')
    feature_courses.short_description = 'Mettre en avant les cours sélectionnés'
    
    def unfeature_courses(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} cours ne sont plus en avant.')
    unfeature_courses.short_description = 'Retirer de la mise en avant'


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    fields = ('order', 'title', 'lesson_type', 'duration', 'is_published', 'is_preview', 'is_mandatory')
    ordering = ('order',)


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'course', 'order', 'lessons_count', 'total_duration_display', 
        'is_published', 'is_free', 'created_at'
    )
    list_filter = ('is_published', 'is_free', 'course__status', 'created_at')
    search_fields = ('title', 'description', 'course__title')
    ordering = ('course', 'order')
    readonly_fields = ('lessons_count', 'total_duration_display', 'created_at', 'updated_at')
    inlines = [LessonInline]
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('course', 'title', 'description', 'order')
        }),
        ('Configuration', {
            'fields': ('is_free', 'estimated_duration', 'prerequisites', 'learning_objectives')
        }),
        ('Publication', {
            'fields': ('is_published', 'publish_date')
        }),
        ('Statistiques', {
            'fields': ('lessons_count', 'total_duration_display'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def lessons_count(self, obj):
        return obj.total_lessons
    lessons_count.short_description = 'Leçons'
    
    def total_duration_display(self, obj):
        duration = obj.total_duration
        if duration > 0:
            hours = int(duration)
            minutes = int((duration - hours) * 60)
            return f"{hours}h {minutes}min"
        return "Non calculée"
    total_duration_display.short_description = 'Durée totale'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('course')


class LessonResourceInline(admin.TabularInline):
    model = LessonResource
    extra = 0
    fields = ('title', 'resource_type', 'file', 'url', 'is_downloadable', 'order')
    ordering = ('order',)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'module', 'order', 'lesson_type', 'duration_display',
        'is_published', 'is_preview', 'is_mandatory', 'has_content_display'
    )
    list_filter = (
        'lesson_type', 'is_published', 'is_preview', 'is_mandatory',
        'module__course__status', 'created_at'
    )
    search_fields = ('title', 'description', 'content', 'module__title', 'module__course__title')
    ordering = ('module', 'order')
    readonly_fields = (
        'duration_display', 'has_content_display', 'content_url_display',
        'created_at', 'updated_at'
    )
    inlines = [LessonResourceInline]
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('module', 'title', 'description', 'order', 'lesson_type')
        }),
        ('Contenu', {
            'fields': ('content',)
        }),
        ('Médias et fichiers', {
            'fields': (
                'video_url', 'video_file', 'audio_file', 
                'document_file', 'external_url'
            ),
            'classes': ('collapse',)
        }),
        ('Paramètres', {
            'fields': ('duration', 'is_preview', 'is_mandatory', 'is_published')
        }),
        ('Métadonnées', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Informations techniques', {
            'fields': (
                'duration_display', 'has_content_display', 'content_url_display'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def duration_display(self, obj):
        if obj.duration:
            total_seconds = int(obj.duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            if hours > 0:
                return f"{hours}h {minutes}min {seconds}s"
            elif minutes > 0:
                return f"{minutes}min {seconds}s"
            else:
                return f"{seconds}s"
        return "Non définie"
    duration_display.short_description = 'Durée'
    
    def has_content_display(self, obj):
        return "✅" if obj.has_content() else "❌"
    has_content_display.short_description = 'A du contenu'
    
    def content_url_display(self, obj):
        url = obj.get_content_url()
        if url:
            return format_html('<a href="{}" target="_blank">{}</a>', url, url[:50] + '...' if len(url) > 50 else url)
        return "Aucune"
    content_url_display.short_description = 'URL du contenu'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('module__course')


@admin.register(LessonResource)
class LessonResourceAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'lesson', 'resource_type', 'is_downloadable', 
        'has_file', 'has_url', 'order', 'created_at'
    )
    list_filter = ('resource_type', 'is_downloadable', 'created_at')
    search_fields = ('title', 'description', 'lesson__title', 'lesson__module__title')
    ordering = ('lesson', 'order')
    readonly_fields = ('has_file', 'has_url', 'resource_url_display', 'created_at')
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('lesson', 'title', 'description', 'resource_type', 'order')
        }),
        ('Fichier ou URL', {
            'fields': ('file', 'url', 'is_downloadable')
        }),
        ('Informations techniques', {
            'fields': ('has_file', 'has_url', 'resource_url_display'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def has_file(self, obj):
        return "✅" if obj.file else "❌"
    has_file.short_description = 'A un fichier'
    
    def has_url(self, obj):
        return "✅" if obj.url else "❌"
    has_url.short_description = 'A une URL'
    
    def resource_url_display(self, obj):
        url = obj.get_resource_url()
        if url:
            return format_html('<a href="{}" target="_blank">{}</a>', url, url[:50] + '...' if len(url) > 50 else url)
        return "Aucune"
    resource_url_display.short_description = 'URL de la ressource'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('lesson__module__course')


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'course', 'status', 'progress_percentage', 
        'enrolled_at', 'amount_paid'
    ]
    list_filter = ['status', 'enrolled_at', 'course__category']
    search_fields = ['user__username', 'user__email', 'course__title']
    readonly_fields = ['enrolled_at', 'progress_percentage']
    list_editable = ['status']
    
    fieldsets = (
        ('Inscription', {
            'fields': ('user', 'course', 'status', 'enrolled_at')
        }),
        ('Progression', {
            'fields': ('progress_percentage', 'current_lesson', 'started_at', 'completed_at', 'last_accessed')
        }),
        ('Paiement', {
            'fields': ('amount_paid', 'payment_date', 'transaction_id')
        }),
    )


@admin.register(CourseFavorite)
class CourseFavoriteAdmin(admin.ModelAdmin):
    list_display = ['user', 'course', 'added_at']
    list_filter = ['added_at', 'course__category']
    search_fields = ['user__username', 'user__email', 'course__title']
    readonly_fields = ['added_at']


@admin.register(LessonCompletion)
class LessonCompletionAdmin(admin.ModelAdmin):
    list_display = ['enrollment', 'lesson', 'completed_at', 'time_spent']
    list_filter = ['completed_at', 'lesson__module__course']
    search_fields = ['enrollment__user__username', 'lesson__title']
    readonly_fields = ['completed_at']


@admin.register(CourseReview)
class CourseReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'course', 'rating', 'is_approved', 'created_at']
    list_filter = ['rating', 'is_approved', 'created_at', 'course__category']
    search_fields = ['user__username', 'course__title', 'title']
    list_editable = ['is_approved']
    readonly_fields = ['created_at', 'updated_at']


# ==================== ADMINISTRATION TARIFICATION ====================

@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'symbol', 'exchange_rate_to_base', 'is_active', 'updated_at']
    list_filter = ['is_active', 'updated_at']
    search_fields = ['code', 'name']
    list_editable = ['exchange_rate_to_base', 'is_active']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('code', 'name', 'symbol', 'is_active')
        }),
        ('Taux de change', {
            'fields': ('exchange_rate_to_base',),
            'description': 'Taux de change vers la devise de base (XAF). 1 XAF = 1.0000'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_currencies', 'deactivate_currencies']
    
    def activate_currencies(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} devise(s) activée(s).')
    activate_currencies.short_description = 'Activer les devises sélectionnées'
    
    def deactivate_currencies(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} devise(s) désactivée(s).')
    deactivate_currencies.short_description = 'Désactiver les devises sélectionnées'


@admin.register(PricingTier)
class PricingTierAdmin(admin.ModelAdmin):
    list_display = ['name', 'discount_percentage', 'countries_display', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    list_editable = ['discount_percentage', 'is_active']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Configuration géographique', {
            'fields': ('countries',),
            'description': 'Liste des codes pays ISO (ex: ["CM", "SN", "CI"])'
        }),
        ('Réduction', {
            'fields': ('discount_percentage',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def countries_display(self, obj):
        if obj.countries:
            return ', '.join(obj.countries)
        return 'Aucun pays'
    countries_display.short_description = 'Pays'


class PricingModelInline(admin.StackedInline):
    model = PricingModel
    extra = 0
    fieldsets = (
        ('Configuration de base', {
            'fields': ('pricing_type', 'base_price', 'base_currency', 'is_active')
        }),
        ('Essai gratuit', {
            'fields': ('has_free_trial', 'trial_duration_days', 'trial_access_type'),
            'classes': ('collapse',)
        }),
        ('Modules individuels', {
            'fields': ('allow_individual_modules', 'module_price_percentage'),
            'classes': ('collapse',)
        }),
        ('Abonnement', {
            'fields': ('subscription_period',),
            'classes': ('collapse',)
        }),
        ('Paiement échelonné', {
            'fields': ('supports_installments', 'max_installments'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PricingModel)
class PricingModelAdmin(admin.ModelAdmin):
    list_display = [
        'course', 'pricing_type', 'base_price', 'base_currency', 
        'has_free_trial', 'allow_individual_modules', 'is_active'
    ]
    list_filter = [
        'pricing_type', 'base_currency', 'has_free_trial', 
        'allow_individual_modules', 'is_active'
    ]
    search_fields = ['course__title']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Configuration de base', {
            'fields': ('course', 'pricing_type', 'base_price', 'base_currency', 'is_active')
        }),
        ('Essai gratuit', {
            'fields': ('has_free_trial', 'trial_duration_days', 'trial_access_type'),
            'classes': ('collapse',)
        }),
        ('Modules individuels', {
            'fields': ('allow_individual_modules', 'module_price_percentage'),
            'classes': ('collapse',)
        }),
        ('Abonnement', {
            'fields': ('subscription_period',),
            'classes': ('collapse',)
        }),
        ('Paiement échelonné', {
            'fields': ('supports_installments', 'max_installments'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CourseBundle)
class CourseBundleAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'price', 'currency', 'courses_count_display', 'savings_amount', 
        'savings_percentage', 'is_valid_display', 'current_purchases'
    ]
    list_filter = ['is_active', 'currency', 'created_at']
    search_fields = ['name', 'description']
    filter_horizontal = ['courses']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = [
        'individual_total_price', 'savings_amount', 'savings_percentage',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('name', 'slug', 'description', 'thumbnail')
        }),
        ('Cours inclus', {
            'fields': ('courses',)
        }),
        ('Prix et économies', {
            'fields': ('price', 'currency', 'individual_total_price', 'savings_amount', 'savings_percentage')
        }),
        ('Configuration', {
            'fields': ('is_active', 'valid_from', 'valid_until', 'max_purchases', 'current_purchases')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def courses_count_display(self, obj):
        return obj.courses_count
    courses_count_display.short_description = 'Nb cours'
    
    def is_valid_display(self, obj):
        if obj.is_valid:
            return format_html('<span style="color: green;">✅ Valide</span>')
        return format_html('<span style="color: red;">❌ Invalide</span>')
    is_valid_display.short_description = 'Statut'
    
    actions = ['calculate_savings', 'activate_bundles', 'deactivate_bundles']
    
    def calculate_savings(self, request, queryset):
        count = 0
        for bundle in queryset:
            bundle.calculate_savings()
            bundle.save()
            count += 1
        self.message_user(request, f'Économies recalculées pour {count} bundle(s).')
    calculate_savings.short_description = 'Recalculer les économies'
    
    def activate_bundles(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} bundle(s) activé(s).')
    activate_bundles.short_description = 'Activer les bundles'
    
    def deactivate_bundles(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} bundle(s) désactivé(s).')
    deactivate_bundles.short_description = 'Désactiver les bundles'


@admin.register(PromotionCode)
class PromotionCodeAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'name', 'discount_type', 'discount_value', 'current_uses',
        'max_uses', 'is_valid_display', 'valid_until'
    ]
    list_filter = [
        'discount_type', 'is_active', 'new_users_only', 
        'valid_from', 'valid_until'
    ]
    search_fields = ['code', 'name', 'description']
    filter_horizontal = ['applicable_courses', 'applicable_bundles', 'eligible_users']
    readonly_fields = ['current_uses', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('code', 'name', 'description', 'is_active')
        }),
        ('Type de réduction', {
            'fields': ('discount_type', 'discount_value', 'max_discount_amount')
        }),
        ('Éligibilité', {
            'fields': (
                'applicable_courses', 'applicable_bundles', 
                'minimum_purchase_amount', 'eligible_users', 'new_users_only'
            )
        }),
        ('Limites d\'usage', {
            'fields': ('usage_type', 'max_uses', 'max_uses_per_user', 'current_uses')
        }),
        ('Validité temporelle', {
            'fields': ('valid_from', 'valid_until')
        }),
        ('Configuration avancée', {
            'fields': ('is_combinable',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_valid_display(self, obj):
        if obj.is_valid:
            return format_html('<span style="color: green;">✅ Valide</span>')
        return format_html('<span style="color: red;">❌ Expiré</span>')
    is_valid_display.short_description = 'Statut'
    
    actions = ['activate_codes', 'deactivate_codes', 'reset_usage_count']
    
    def activate_codes(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} code(s) activé(s).')
    activate_codes.short_description = 'Activer les codes'
    
    def deactivate_codes(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} code(s) désactivé(s).')
    deactivate_codes.short_description = 'Désactiver les codes'
    
    def reset_usage_count(self, request, queryset):
        updated = queryset.update(current_uses=0)
        self.message_user(request, f'Compteur d\'usage remis à zéro pour {updated} code(s).')
    reset_usage_count.short_description = 'Remettre compteur à zéro'


@admin.register(PromotionCodeUsage)
class PromotionCodeUsageAdmin(admin.ModelAdmin):
    list_display = [
        'promotion_code', 'user', 'course', 'bundle', 
        'original_price', 'discount_amount', 'final_price', 'used_at'
    ]
    list_filter = ['used_at', 'currency', 'promotion_code__discount_type']
    search_fields = [
        'promotion_code__code', 'user__username', 'user__email',
        'course__title', 'bundle__name', 'transaction_reference'
    ]
    readonly_fields = ['used_at']
    
    fieldsets = (
        ('Utilisation', {
            'fields': ('promotion_code', 'user', 'course', 'bundle', 'used_at')
        }),
        ('Détails financiers', {
            'fields': ('original_price', 'discount_amount', 'final_price', 'currency')
        }),
        ('Transaction', {
            'fields': ('transaction_reference',)
        }),
    )
    
    def has_add_permission(self, request):
        return False  # Les usages sont créés automatiquement


@admin.register(ModulePricing)
class ModulePricingAdmin(admin.ModelAdmin):
    list_display = [
        'module', 'price', 'currency', 'is_available_individually',
        'requires_previous_modules'
    ]
    list_filter = ['currency', 'is_available_individually', 'requires_previous_modules']
    search_fields = ['module__title', 'module__course__title']
    filter_horizontal = ['prerequisite_modules']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('module', 'price', 'currency', 'is_available_individually')
        }),
        ('Prérequis', {
            'fields': ('requires_previous_modules', 'prerequisite_modules'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# Configuration de l'administration
admin.site.site_header = "eSchool - Administration"
admin.site.site_title = "eSchool Admin"
admin.site.index_title = "Tableau de bord d'administration"
