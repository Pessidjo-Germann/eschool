from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    # Liste des cours
    path('', views.courses_list, name='courses_list'),
    
    # Liste des catégories
    path('categories/', views.categories_list, name='categories_list'),
    
    # Mes cours et favoris
    path('my-courses/', views.my_courses, name='my_courses'),
    path('my-favorites/', views.my_favorites, name='my_favorites'),
    
    # Actions sur les cours
    path('<slug:slug>/enroll/', views.enroll_course, name='enroll_course'),
    path('<slug:slug>/toggle-favorite/', views.toggle_favorite, name='toggle_favorite'),
    
    # Détail d'une catégorie
    path('category/<slug:slug>/', views.category_detail, name='category_detail'),
    
    # Détail d'un cours
    path('<slug:slug>/', views.course_detail, name='course_detail'),
    
    # Détail d'une leçon
    path('<slug:course_slug>/lesson/<int:lesson_id>/', views.lesson_detail, name='lesson_detail'),
]