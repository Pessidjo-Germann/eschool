from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, instructor_views, student_views

app_name = 'quiz'

# Router pour les API REST
router = DefaultRouter()
router.register(r'quizzes', views.QuizViewSet, basename='quiz')
router.register(r'attempts', views.QuizAttemptViewSet, basename='attempt')

urlpatterns = [
    # API Routes
    path('api/', include(router.urls)),
    
    # Interface Web Instructeur
    path('instructor/', include([
        # Gestion des quiz
        path('', instructor_views.quiz_list, name='quiz_list'),
        path('create/', instructor_views.quiz_create, name='quiz_create'),
        path('<uuid:pk>/', instructor_views.quiz_detail, name='quiz_detail'),
        path('<uuid:pk>/edit/', instructor_views.quiz_edit, name='quiz_edit'),
        path('<uuid:pk>/delete/', instructor_views.quiz_delete, name='quiz_delete'),
        path('<uuid:pk>/duplicate/', instructor_views.quiz_duplicate, name='quiz_duplicate'),
        path('<uuid:pk>/publish/', instructor_views.quiz_publish, name='quiz_publish'),
        path('<uuid:pk>/preview/', instructor_views.quiz_preview, name='quiz_preview'),
        path('<uuid:pk>/analytics/', instructor_views.quiz_analytics, name='quiz_analytics'),
        
        # Gestion des questions
        path('<uuid:quiz_pk>/question/create/', instructor_views.question_create, name='question_create'),
        path('<uuid:quiz_pk>/question/<uuid:pk>/edit/', instructor_views.question_edit, name='question_edit'),
        path('<uuid:quiz_pk>/question/<uuid:pk>/choices/', instructor_views.question_edit_choices, name='question_edit_choices'),
        path('<uuid:quiz_pk>/question/<uuid:pk>/delete/', instructor_views.question_delete, name='question_delete'),
        
        # AJAX endpoints
        path('ajax/lessons/', instructor_views.get_lessons_by_course, name='ajax_lessons'),
        path('ajax/questions/', instructor_views.get_questions_by_quiz, name='ajax_questions'),
        path('<uuid:quiz_pk>/ajax/reorder/', instructor_views.reorder_questions, name='ajax_reorder_questions'),
        path('<uuid:quiz_pk>/question/<uuid:pk>/ajax/edit/', instructor_views.question_quick_edit, name='ajax_question_edit'),
    ])),
    
    # Interface Web Étudiant
    path('student/', include([
        # Gestion des quiz pour étudiants
        path('', student_views.quiz_list, name='student_quiz_list'),
        path('<uuid:quiz_id>/', student_views.quiz_detail, name='student_quiz_detail'),
        path('<uuid:quiz_id>/start/', student_views.quiz_start, name='student_quiz_start'),
        
        # Passage du quiz
        path('attempt/<uuid:attempt_id>/', student_views.quiz_take, name='student_quiz_take'),
        path('attempt/<uuid:attempt_id>/save/', student_views.quiz_save_answer, name='student_quiz_save'),
        path('attempt/<uuid:attempt_id>/submit/', student_views.quiz_submit, name='student_quiz_submit'),
        path('attempt/<uuid:attempt_id>/resume/', student_views.quiz_resume, name='student_quiz_resume'),
        
        # Résultats et révision
        path('attempt/<uuid:attempt_id>/results/', student_views.quiz_results, name='student_quiz_results'),
        path('attempt/<uuid:attempt_id>/review/', student_views.quiz_review, name='student_quiz_review'),
    ])),
]