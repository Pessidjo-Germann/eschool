from rest_framework import permissions


class IsInstructorOrReadOnly(permissions.BasePermission):
    """
    Permission personnalisée pour permettre aux instructeurs de créer/modifier/supprimer
    et lecture seule pour les autres utilisateurs.
    """
    
    def has_permission(self, request, view):
        # Lecture autorisée pour tous
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Écriture seulement pour les instructeurs authentifiés
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role in ['instructor', 'admin']
        )


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission personnalisée pour permettre aux propriétaires de modifier leur contenu
    et lecture seule pour les autres.
    """
    
    def has_object_permission(self, request, view, obj):
        # Lecture autorisée pour tous
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Vérification selon le type d'objet
        if hasattr(obj, 'instructor'):
            # Cours
            return obj.instructor == request.user
        elif hasattr(obj, 'course'):
            # Module
            return obj.course.instructor == request.user
        elif hasattr(obj, 'module'):
            # Leçon
            return obj.module.course.instructor == request.user
        elif hasattr(obj, 'lesson'):
            # Ressource de leçon
            return obj.lesson.module.course.instructor == request.user
        
        return False


class IsInstructor(permissions.BasePermission):
    """
    Permission pour les instructeurs uniquement.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role in ['instructor', 'admin']
        )


class IsOwner(permissions.BasePermission):
    """
    Permission pour les propriétaires uniquement.
    """
    
    def has_object_permission(self, request, view, obj):
        # Vérification selon le type d'objet
        if hasattr(obj, 'user'):
            # Inscription, Favori, Avis
            return obj.user == request.user
        elif hasattr(obj, 'instructor'):
            # Cours
            return obj.instructor == request.user
        
        return False


class IsEnrolledOrInstructor(permissions.BasePermission):
    """
    Permission pour les étudiants inscrits ou les instructeurs du cours.
    """
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # L'instructeur a toujours accès
        course = None
        if hasattr(obj, 'course'):
            course = obj.course
        elif hasattr(obj, 'module'):
            course = obj.module.course
        elif hasattr(obj, 'lesson'):
            course = obj.lesson.module.course
        
        if course and course.instructor == request.user:
            return True
        
        # Vérifier l'inscription pour les étudiants
        if course and request.user.role == 'student':
            return course.enrollments.filter(
                user=request.user, 
                status='active'
            ).exists()
        
        return False


class CanAccessLesson(permissions.BasePermission):
    """
    Permission pour accéder à une leçon selon les règles métier.
    """
    
    def has_object_permission(self, request, view, obj):
        # obj est une Lesson
        if not hasattr(obj, 'module'):
            return False
        
        course = obj.module.course
        
        # Leçons preview accessibles à tous
        if obj.is_preview:
            return True
        
        if not request.user or not request.user.is_authenticated:
            return False
        
        # L'instructeur a toujours accès
        if course.instructor == request.user:
            return True
        
        # Vérifier l'inscription pour les étudiants
        if request.user.role == 'student':
            return course.enrollments.filter(
                user=request.user,
                status='active'
            ).exists()
        
        return False