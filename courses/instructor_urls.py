from django.urls import path
from . import instructor_views

app_name = 'instructor'

urlpatterns = [
    # === GESTION DES COURS ===
    # Liste et tableau de bord
    path('', instructor_views.courses_management, name='courses'),
    
    # CRUD des cours
    path('course/create/', instructor_views.course_create, name='course_create'),
    path('course/<uuid:pk>/', instructor_views.course_detail, name='course_detail'),
    path('course/<uuid:pk>/edit/', instructor_views.course_edit, name='course_edit'),
    path('course/<uuid:pk>/delete/', instructor_views.course_delete, name='course_delete'),
    
    # Actions sur les cours
    path('course/<uuid:pk>/publish/', instructor_views.course_publish, name='course_publish'),
    path('course/<uuid:pk>/unpublish/', instructor_views.course_unpublish, name='course_unpublish'),
    path('course/<uuid:pk>/analytics/', instructor_views.course_analytics, name='course_analytics'),
    
    # === GESTION DES MODULES ===
    path('course/<uuid:course_pk>/module/create/', instructor_views.module_create, name='module_create'),
    path('course/<uuid:course_pk>/module/<int:pk>/edit/', instructor_views.module_edit, name='module_edit'),
    path('course/<uuid:course_pk>/module/<int:pk>/delete/', instructor_views.module_delete, name='module_delete'),
    path('course/<uuid:course_pk>/module/<int:pk>/publish/', instructor_views.module_publish, name='module_publish'),
    path('course/<uuid:course_pk>/module/<int:pk>/unpublish/', instructor_views.module_unpublish, name='module_unpublish'),
    
    # === GESTION DES LEÇONS ===
    path('course/<uuid:course_pk>/module/<int:module_pk>/lesson/create/', 
         instructor_views.lesson_create, name='lesson_create'),
    path('course/<uuid:course_pk>/module/<int:module_pk>/lesson/<int:pk>/', 
         instructor_views.lesson_detail, name='lesson_detail'),
    path('course/<uuid:course_pk>/module/<int:module_pk>/lesson/<int:pk>/edit/', 
         instructor_views.lesson_edit, name='lesson_edit'),
    path('course/<uuid:course_pk>/module/<int:module_pk>/lesson/<int:pk>/publish/', 
         instructor_views.lesson_publish, name='lesson_publish'),
    path('course/<uuid:course_pk>/module/<int:module_pk>/lesson/<int:pk>/unpublish/', 
         instructor_views.lesson_unpublish, name='lesson_unpublish'),
    path('course/<uuid:course_pk>/module/<int:module_pk>/lesson/<int:pk>/delete/', 
         instructor_views.lesson_delete, name='lesson_delete'),
    
    # === AJAX ENDPOINTS ===
    path('ajax/upload-media/', instructor_views.upload_media, name='upload_media'),
]