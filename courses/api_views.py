from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from .models import (
    Category, Course, Tag, Module, Lesson, LessonResource,
    Enrollment, CourseFavorite, CourseReview
)
from .serializers import (
    CategorySerializer, TagSerializer, CourseListSerializer,
    CourseDetailSerializer, CourseCreateUpdateSerializer,
    ModuleDetailSerializer, ModuleSerializer,
    LessonDetailSerializer, LessonSerializer, LessonResourceSerializer,
    EnrollmentSerializer, CourseFavoriteSerializer, CourseReviewSerializer
)
from .permissions import IsInstructorOrReadOnly, IsOwnerOrReadOnly


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour les catégories (lecture seule)
    """
    queryset = Category.objects.filter(is_active=True).order_by('order', 'name')
    serializer_class = CategorySerializer
    lookup_field = 'slug'
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Filtrer par parent si spécifié
        parent_id = self.request.query_params.get('parent')
        if parent_id:
            if parent_id == 'null':
                queryset = queryset.filter(parent=None)
            else:
                queryset = queryset.filter(parent_id=parent_id)
        return queryset


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour les tags (lecture seule)
    """
    queryset = Tag.objects.all().order_by('name')
    serializer_class = TagSerializer
    lookup_field = 'slug'
    permission_classes = [permissions.AllowAny]


class CourseViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour les cours avec CRUD complet pour les formateurs
    """
    serializer_class = CourseListSerializer
    permission_classes = [IsInstructorOrReadOnly]
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'difficulty', 'language', 'is_free', 'is_featured', 'status']
    search_fields = ['title', 'short_description', 'description', 'instructor__first_name', 'instructor__last_name']
    ordering_fields = ['title', 'created_at', 'updated_at', 'price', 'enrollment_count']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = Course.objects.select_related('category', 'instructor').prefetch_related('tags')
        
        # Les instructeurs ne voient que leurs cours
        if self.request.user.is_authenticated and self.request.user.role == 'instructor':
            if self.action in ['list', 'retrieve', 'update', 'partial_update', 'destroy']:
                queryset = queryset.filter(instructor=self.request.user)
        
        # Pour les utilisateurs publics, seulement les cours publiés
        if not self.request.user.is_authenticated or self.request.user.role not in ['instructor', 'admin']:
            queryset = queryset.filter(status='published')
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CourseDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return CourseCreateUpdateSerializer
        return CourseListSerializer
    
    def perform_create(self, serializer):
        serializer.save(instructor=self.request.user)
    
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Publier un cours"""
        course = self.get_object()
        
        # Vérifications avant publication
        if not course.modules.filter(is_published=True).exists():
            return Response(
                {'error': 'Le cours doit avoir au moins un module publié.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Vérifier qu'il y a du contenu
        has_content = False
        for module in course.modules.filter(is_published=True):
            if module.lessons.filter(is_published=True).exists():
                has_content = True
                break
        
        if not has_content:
            return Response(
                {'error': 'Le cours doit avoir au moins une leçon publiée.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        course.status = 'published'
        course.publish_date = timezone.now()
        course.save()
        
        return Response({'message': 'Cours publié avec succès.'})
    
    @action(detail=True, methods=['post'])
    def unpublish(self, request, pk=None):
        """Dépublier un cours"""
        course = self.get_object()
        course.status = 'draft'
        course.save()
        
        return Response({'message': 'Cours dépublié avec succès.'})
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Dupliquer un cours"""
        original_course = self.get_object()
        
        # Créer une copie du cours
        new_course = Course.objects.create(
            title=f"{original_course.title} (Copie)",
            short_description=original_course.short_description,
            description=original_course.description,
            category=original_course.category,
            instructor=self.request.user,
            difficulty=original_course.difficulty,
            language=original_course.language,
            price=original_course.price,
            is_free=original_course.is_free,
            prerequisites=original_course.prerequisites,
            learning_objectives=original_course.learning_objectives,
            target_audience=original_course.target_audience,
            has_certificate=original_course.has_certificate,
            status='draft'
        )
        
        # Copier les tags
        new_course.tags.set(original_course.tags.all())
        
        # Copier les modules et leçons
        for module in original_course.modules.all():
            new_module = Module.objects.create(
                course=new_course,
                title=module.title,
                description=module.description,
                order=module.order,
                is_published=False,
                is_free=module.is_free,
                price=module.price
            )
            
            # Copier les leçons
            for lesson in module.lessons.all():
                Lesson.objects.create(
                    module=new_module,
                    title=lesson.title,
                    description=lesson.description,
                    content=lesson.content,
                    order=lesson.order,
                    lesson_type=lesson.lesson_type,
                    duration=lesson.duration,
                    video_url=lesson.video_url,
                    external_url=lesson.external_url,
                    is_published=False,
                    is_preview=False,
                    is_mandatory=lesson.is_mandatory,
                    notes=lesson.notes
                )
        
        serializer = CourseDetailSerializer(new_course, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Statistiques du cours pour l'instructeur"""
        course = self.get_object()
        
        enrollments = course.enrollments.all()
        reviews = course.reviews.filter(is_approved=True)
        
        analytics_data = {
            'total_enrollments': enrollments.count(),
            'active_enrollments': enrollments.filter(status='active').count(),
            'completed_enrollments': enrollments.filter(status='completed').count(),
            'total_revenue': sum(e.amount_paid for e in enrollments),
            'average_rating': reviews.aggregate(Avg('rating'))['rating__avg'],
            'total_reviews': reviews.count(),
            'view_count': course.view_count,
            'completion_rate': 0,  # À calculer selon la logique métier
            'monthly_enrollments': {},  # À implémenter selon les besoins
        }
        
        return Response(analytics_data)


class ModuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour les modules d'un cours
    """
    serializer_class = ModuleSerializer
    permission_classes = [IsInstructorOrReadOnly, IsOwnerOrReadOnly]
    
    def get_queryset(self):
        course_pk = self.kwargs.get('course_pk')
        if course_pk:
            course = get_object_or_404(Course, pk=course_pk)
            # Vérifier les permissions pour le cours
            if (self.request.user.is_authenticated and 
                self.request.user.role == 'instructor' and 
                course.instructor != self.request.user):
                return Module.objects.none()
            
            return course.modules.all().order_by('order')
        return Module.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ModuleDetailSerializer
        return ModuleSerializer
    
    def perform_create(self, serializer):
        course_pk = self.kwargs.get('course_pk')
        course = get_object_or_404(Course, pk=course_pk, instructor=self.request.user)
        serializer.save(course=course)
    
    @action(detail=True, methods=['post'])
    def reorder(self, request, course_pk=None, pk=None):
        """Réorganiser l'ordre des modules"""
        new_order = request.data.get('order')
        if new_order is None:
            return Response(
                {'error': 'Le paramètre "order" est requis.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        module = self.get_object()
        module.order = new_order
        module.save()
        
        return Response({'message': 'Ordre mis à jour avec succès.'})


class LessonViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour les leçons d'un module
    """
    serializer_class = LessonSerializer
    permission_classes = [IsInstructorOrReadOnly, IsOwnerOrReadOnly]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        course_pk = self.kwargs.get('course_pk')
        module_pk = self.kwargs.get('module_pk')
        
        if course_pk and module_pk:
            course = get_object_or_404(Course, pk=course_pk)
            module = get_object_or_404(Module, pk=module_pk, course=course)
            
            # Vérifier les permissions pour le cours
            if (self.request.user.is_authenticated and 
                self.request.user.role == 'instructor' and 
                course.instructor != self.request.user):
                return Lesson.objects.none()
            
            return module.lessons.all().order_by('order')
        return Lesson.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return LessonDetailSerializer
        return LessonSerializer
    
    def perform_create(self, serializer):
        course_pk = self.kwargs.get('course_pk')
        module_pk = self.kwargs.get('module_pk')
        
        course = get_object_or_404(Course, pk=course_pk, instructor=self.request.user)
        module = get_object_or_404(Module, pk=module_pk, course=course)
        
        serializer.save(module=module)
    
    @action(detail=True, methods=['post'])
    def reorder(self, request, course_pk=None, module_pk=None, pk=None):
        """Réorganiser l'ordre des leçons"""
        new_order = request.data.get('order')
        if new_order is None:
            return Response(
                {'error': 'Le paramètre "order" est requis.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        lesson = self.get_object()
        lesson.order = new_order
        lesson.save()
        
        return Response({'message': 'Ordre mis à jour avec succès.'})


class LessonResourceViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour les ressources d'une leçon
    """
    serializer_class = LessonResourceSerializer
    permission_classes = [IsInstructorOrReadOnly, IsOwnerOrReadOnly]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        lesson_pk = self.kwargs.get('lesson_pk')
        if lesson_pk:
            lesson = get_object_or_404(Lesson, pk=lesson_pk)
            
            # Vérifier les permissions
            if (self.request.user.is_authenticated and 
                self.request.user.role == 'instructor' and 
                lesson.module.course.instructor != self.request.user):
                return LessonResource.objects.none()
            
            return lesson.resources.all().order_by('order')
        return LessonResource.objects.none()
    
    def perform_create(self, serializer):
        lesson_pk = self.kwargs.get('lesson_pk')
        lesson = get_object_or_404(Lesson, pk=lesson_pk)
        
        # Vérifier que l'utilisateur est propriétaire du cours
        if lesson.module.course.instructor != self.request.user:
            return Response(
                {'error': 'Permission refusée.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer.save(lesson=lesson)


# ViewSets pour les autres fonctionnalités

class EnrollmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour les inscriptions (lecture seule pour les instructeurs)
    """
    serializer_class = EnrollmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.role == 'instructor':
            # Les instructeurs voient les inscriptions à leurs cours
            return Enrollment.objects.filter(
                course__instructor=self.request.user
            ).select_related('user', 'course')
        elif self.request.user.role == 'student':
            # Les étudiants voient leurs propres inscriptions
            return Enrollment.objects.filter(
                user=self.request.user
            ).select_related('course')
        return Enrollment.objects.none()


class CourseReviewViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour les avis sur les cours
    """
    serializer_class = CourseReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['rating', 'course']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return CourseReview.objects.filter(is_approved=True).select_related('user', 'course')