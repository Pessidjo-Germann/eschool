from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from .api_views import (
    CategoryViewSet, TagViewSet, CourseViewSet,
    ModuleViewSet, LessonViewSet, LessonResourceViewSet,
    EnrollmentViewSet, CourseReviewViewSet
)

# Router principal
router = DefaultRouter()
router.register('categories', CategoryViewSet)
router.register('tags', TagViewSet)
router.register('courses', CourseViewSet, basename='course')
router.register('enrollments', EnrollmentViewSet, basename='enrollment')
router.register('reviews', CourseReviewViewSet, basename='review')

# Routers imbriqués pour la hiérarchie cours > modules > leçons
courses_router = routers.NestedDefaultRouter(router, 'courses', lookup='course')
courses_router.register('modules', ModuleViewSet, basename='course-modules')

modules_router = routers.NestedDefaultRouter(courses_router, 'modules', lookup='module')
modules_router.register('lessons', LessonViewSet, basename='module-lessons')

lessons_router = routers.NestedDefaultRouter(modules_router, 'lessons', lookup='lesson')
lessons_router.register('resources', LessonResourceViewSet, basename='lesson-resources')

app_name = 'courses_api'

urlpatterns = [
    # Routes principales
    path('', include(router.urls)),
    
    # Routes imbriquées
    path('', include(courses_router.urls)),
    path('', include(modules_router.urls)),
    path('', include(lessons_router.urls)),
]

"""
Structure de l'API:

/api/courses/categories/
/api/courses/tags/
/api/courses/courses/
/api/courses/courses/{id}/
/api/courses/courses/{id}/publish/
/api/courses/courses/{id}/unpublish/
/api/courses/courses/{id}/duplicate/
/api/courses/courses/{id}/analytics/

/api/courses/courses/{course_id}/modules/
/api/courses/courses/{course_id}/modules/{id}/
/api/courses/courses/{course_id}/modules/{id}/reorder/

/api/courses/courses/{course_id}/modules/{module_id}/lessons/
/api/courses/courses/{course_id}/modules/{module_id}/lessons/{id}/
/api/courses/courses/{course_id}/modules/{module_id}/lessons/{id}/reorder/

/api/courses/courses/{course_id}/modules/{module_id}/lessons/{lesson_id}/resources/
/api/courses/courses/{course_id}/modules/{module_id}/lessons/{lesson_id}/resources/{id}/

/api/courses/enrollments/
/api/courses/reviews/
"""