from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.contrib.auth import get_user_model
from .models import (
    Category, Course, Tag, Module, Lesson, LessonResource,
    Enrollment, CourseFavorite, CourseReview
)

User = get_user_model()


class CategorySerializer(serializers.ModelSerializer):
    """Serializer pour les catégories"""
    subcategories_count = serializers.SerializerMethodField()
    courses_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description', 'parent', 
            'color', 'icon', 'is_active', 'order',
            'subcategories_count', 'courses_count'
        ]
        read_only_fields = ['id', 'slug']
    
    def get_subcategories_count(self, obj):
        return obj.subcategories.filter(is_active=True).count()
    
    def get_courses_count(self, obj):
        return obj.courses.filter(status='published').count()


class TagSerializer(serializers.ModelSerializer):
    """Serializer pour les tags"""
    
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug', 'color']
        read_only_fields = ['id', 'slug']


class InstructorSerializer(serializers.ModelSerializer):
    """Serializer pour les informations instructeur"""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 
            'email', 'full_name', 'profile_picture', 'bio'
        ]
        read_only_fields = ['id', 'username', 'email']
    
    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class LessonResourceSerializer(serializers.ModelSerializer):
    """Serializer pour les ressources de leçon"""
    resource_url = serializers.SerializerMethodField()
    
    class Meta:
        model = LessonResource
        fields = [
            'id', 'title', 'description', 'resource_type', 
            'file', 'url', 'is_downloadable', 'order',
            'resource_url', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_resource_url(self, obj):
        return obj.get_resource_url()


class LessonDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour les leçons"""
    resources = LessonResourceSerializer(many=True, read_only=True)
    content_url = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'description', 'content', 'order',
            'lesson_type', 'duration', 'duration_display',
            'video_url', 'video_file', 'audio_file', 'document_file',
            'external_url', 'is_published', 'is_preview', 'is_mandatory',
            'notes', 'resources', 'content_url', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_content_url(self, obj):
        if obj.video_file:
            return obj.video_file.url
        elif obj.audio_file:
            return obj.audio_file.url
        elif obj.document_file:
            return obj.document_file.url
        return obj.video_url or obj.external_url
    
    def get_duration_display(self, obj):
        if obj.duration:
            total_seconds = int(obj.duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            if hours > 0:
                return f"{hours}h {minutes}min"
            elif minutes > 0:
                return f"{minutes}min {seconds}s"
            else:
                return f"{seconds}s"
        return None


class LessonSerializer(serializers.ModelSerializer):
    """Serializer simple pour les leçons"""
    duration_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'description', 'order', 'lesson_type',
            'duration', 'duration_display', 'is_published', 
            'is_preview', 'is_mandatory'
        ]
        read_only_fields = ['id']
    
    def get_duration_display(self, obj):
        if obj.duration:
            total_seconds = int(obj.duration.total_seconds())
            minutes = total_seconds // 60
            return f"{minutes}min"
        return None


class ModuleDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour les modules"""
    lessons = LessonSerializer(many=True, read_only=True)
    lessons_count = serializers.SerializerMethodField()
    total_duration_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Module
        fields = [
            'id', 'title', 'description', 'order', 'is_published',
            'is_free', 'lessons', 'lessons_count',
            'total_duration_display', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_lessons_count(self, obj):
        return obj.lessons.count()
    
    def get_total_duration_display(self, obj):
        duration = obj.total_duration
        if duration > 0:
            hours = int(duration)
            minutes = int((duration - hours) * 60)
            return f"{hours}h {minutes}min"
        return "0min"


class ModuleSerializer(serializers.ModelSerializer):
    """Serializer simple pour les modules"""
    lessons_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Module
        fields = [
            'id', 'title', 'description', 'order', 'is_published',
            'is_free', 'lessons_count'
        ]
        read_only_fields = ['id']
    
    def get_lessons_count(self, obj):
        return obj.lessons.count()


class CourseListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des cours"""
    category = CategorySerializer(read_only=True)
    instructor = InstructorSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    modules_count = serializers.SerializerMethodField()
    lessons_count = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'short_description', 'thumbnail',
            'category', 'instructor', 'tags', 'difficulty', 'language',
            'price', 'is_free', 'is_featured', 'status', 'publish_date',
            'enrollment_count', 'view_count', 'modules_count', 'lessons_count',
            'duration_display', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'slug', 'enrollment_count', 'view_count', 
            'created_at', 'updated_at'
        ]
    
    def get_modules_count(self, obj):
        return obj.modules.count()
    
    def get_lessons_count(self, obj):
        return sum(module.lessons.count() for module in obj.modules.all())
    
    def get_duration_display(self, obj):
        duration = obj.total_duration
        if duration > 0:
            hours = int(duration)
            minutes = int((duration - hours) * 60)
            return f"{hours}h {minutes}min"
        return "0min"


class CourseDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour un cours"""
    category = CategorySerializer(read_only=True)
    instructor = InstructorSerializer(read_only=True)
    co_instructors = InstructorSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    modules = ModuleDetailSerializer(many=True, read_only=True)
    
    # Champs calculés
    modules_count = serializers.SerializerMethodField()
    lessons_count = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'short_description', 'description',
            'thumbnail', 'category', 'instructor', 'co_instructors', 'tags',
            'difficulty', 'language', 'price', 'is_free', 'is_featured',
            'status', 'publish_date', 'prerequisites', 'learning_objectives',
            'target_audience', 'has_certificate', 'meta_description',
            'enrollment_count', 'view_count', 'modules', 'modules_count',
            'lessons_count', 'duration_display', 'average_rating', 'reviews_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'slug', 'enrollment_count', 'view_count',
            'created_at', 'updated_at'
        ]
    
    def get_modules_count(self, obj):
        return obj.modules.count()
    
    def get_lessons_count(self, obj):
        return sum(module.lessons.count() for module in obj.modules.all())
    
    def get_duration_display(self, obj):
        duration = obj.total_duration
        if duration > 0:
            hours = int(duration)
            minutes = int((duration - hours) * 60)
            return f"{hours}h {minutes}min"
        return "0min"
    
    def get_average_rating(self, obj):
        reviews = obj.reviews.filter(is_approved=True)
        if reviews:
            return round(sum(r.rating for r in reviews) / len(reviews), 1)
        return None
    
    def get_reviews_count(self, obj):
        return obj.reviews.filter(is_approved=True).count()


class CourseCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour créer/modifier un cours"""
    category_id = serializers.IntegerField(write_only=True)
    tags_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    co_instructors_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Course
        fields = [
            'title', 'short_description', 'description', 'thumbnail',
            'category_id', 'tags_ids', 'co_instructors_ids',
            'difficulty', 'language', 'price', 'is_free', 'is_featured',
            'status', 'prerequisites', 'learning_objectives', 'target_audience',
            'has_certificate', 'meta_description', 'meta_keywords'
        ]
    
    def validate_category_id(self, value):
        try:
            category = Category.objects.get(id=value, is_active=True)
            return value
        except Category.DoesNotExist:
            raise serializers.ValidationError("Catégorie invalide.")
    
    def validate_tags_ids(self, value):
        if value:
            existing_tags = Tag.objects.filter(id__in=value)
            if len(existing_tags) != len(value):
                raise serializers.ValidationError("Certains tags sont invalides.")
        return value
    
    def validate_co_instructors_ids(self, value):
        if value:
            existing_instructors = User.objects.filter(
                id__in=value,
                role='instructor',
                is_active=True
            )
            if len(existing_instructors) != len(value):
                raise serializers.ValidationError("Certains co-instructeurs sont invalides.")
        return value
    
    def validate(self, attrs):
        # Validation cohérence prix/gratuité
        if attrs.get('is_free') and attrs.get('price', 0) > 0:
            raise serializers.ValidationError({
                'price': "Un cours gratuit ne peut pas avoir un prix."
            })
        
        if not attrs.get('is_free', True) and attrs.get('price', 0) <= 0:
            raise serializers.ValidationError({
                'price': "Un cours payant doit avoir un prix supérieur à 0."
            })
        
        return attrs
    
    def create(self, validated_data):
        # Extraire les données relationnelles
        category_id = validated_data.pop('category_id')
        tags_ids = validated_data.pop('tags_ids', [])
        co_instructors_ids = validated_data.pop('co_instructors_ids', [])
        
        # Créer le cours
        course = Course.objects.create(
            category_id=category_id,
            instructor=self.context['request'].user,
            **validated_data
        )
        
        # Ajouter les relations Many-to-Many
        if tags_ids:
            course.tags.set(tags_ids)
        if co_instructors_ids:
            course.co_instructors.set(co_instructors_ids)
        
        return course
    
    def update(self, instance, validated_data):
        # Extraire les données relationnelles
        category_id = validated_data.pop('category_id', None)
        tags_ids = validated_data.pop('tags_ids', None)
        co_instructors_ids = validated_data.pop('co_instructors_ids', None)
        
        # Mettre à jour les champs simples
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Mettre à jour la catégorie
        if category_id is not None:
            instance.category_id = category_id
        
        instance.save()
        
        # Mettre à jour les relations Many-to-Many
        if tags_ids is not None:
            instance.tags.set(tags_ids)
        if co_instructors_ids is not None:
            instance.co_instructors.set(co_instructors_ids)
        
        return instance


# Serializers pour les autres modèles

class EnrollmentSerializer(serializers.ModelSerializer):
    """Serializer pour les inscriptions"""
    course = CourseListSerializer(read_only=True)
    user = InstructorSerializer(read_only=True)
    
    class Meta:
        model = Enrollment
        fields = [
            'id', 'user', 'course', 'status', 'progress_percentage',
            'enrolled_at', 'started_at', 'completed_at', 'last_accessed',
            'amount_paid', 'payment_date', 'transaction_id'
        ]
        read_only_fields = [
            'id', 'enrolled_at', 'progress_percentage'
        ]


class CourseFavoriteSerializer(serializers.ModelSerializer):
    """Serializer pour les favoris"""
    course = CourseListSerializer(read_only=True)
    
    class Meta:
        model = CourseFavorite
        fields = ['id', 'course', 'added_at']
        read_only_fields = ['id', 'added_at']


class CourseReviewSerializer(serializers.ModelSerializer):
    """Serializer pour les avis"""
    user = InstructorSerializer(read_only=True)
    course = CourseListSerializer(read_only=True)
    
    class Meta:
        model = CourseReview
        fields = [
            'id', 'user', 'course', 'rating', 'title', 'comment',
            'is_approved', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']