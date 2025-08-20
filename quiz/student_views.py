from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.core.paginator import Paginator
from django.urls import reverse
from django.utils import timezone
from django.db.models import Q, Count, Avg
import json
from datetime import timedelta

from core.permissions import student_required
from .models import Quiz, Question, Choice, QuizAttempt, Answer
from courses.models import Course, Lesson


@login_required
def quiz_list(request):
    """Liste des quiz disponibles pour l'étudiant"""
    # Quiz auxquels l'étudiant a accès via ses cours inscrits
    from courses.models import Enrollment
    enrolled_courses = [enrollment.course for enrollment in Enrollment.objects.filter(user=request.user).select_related('course')]
    
    # Quiz publiés des cours auxquels l'étudiant est inscrit
    available_quizzes = Quiz.objects.filter(
        course__in=enrolled_courses,
        is_published=True
    ).select_related('course', 'lesson', 'instructor').order_by('-created_at')
    
    # Filtrage par recherche
    search = request.GET.get('search', '')
    if search:
        available_quizzes = available_quizzes.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(course__title__icontains=search)
        )
    
    # Filtrage par cours
    course_filter = request.GET.get('course', '')
    if course_filter:
        available_quizzes = available_quizzes.filter(course_id=course_filter)
    
    # Filtrage par difficulté
    difficulty_filter = request.GET.get('difficulty', '')
    if difficulty_filter:
        available_quizzes = available_quizzes.filter(difficulty=difficulty_filter)
    
    # Filtrage par type
    quiz_type_filter = request.GET.get('quiz_type', '')
    if quiz_type_filter:
        available_quizzes = available_quizzes.filter(quiz_type=quiz_type_filter)
    
    # Ajouter les informations sur les tentatives de l'étudiant
    quiz_data = []
    for quiz in available_quizzes:
        attempts = QuizAttempt.objects.filter(quiz=quiz, user=request.user)
        last_attempt = attempts.order_by('-started_at').first()
        best_score = attempts.aggregate(best=Avg('score'))['best']
        
        quiz_data.append({
            'quiz': quiz,
            'attempts_count': attempts.count(),
            'can_attempt': attempts.count() < quiz.max_attempts,
            'last_attempt': last_attempt,
            'best_score': best_score,
            'is_available': quiz.is_available_for_student(request.user),
        })
    
    # Pagination
    paginator = Paginator(quiz_data, 12)
    page_number = request.GET.get('page')
    quizzes = paginator.get_page(page_number)
    
    context = {
        'quizzes': quizzes,
        'enrolled_courses': enrolled_courses,
        'search': search,
        'current_course': course_filter,
        'current_difficulty': difficulty_filter,
        'current_quiz_type': quiz_type_filter,
        'difficulty_choices': Quiz.DIFFICULTY_LEVELS,
        'quiz_type_choices': Quiz.QUIZ_TYPES,
    }
    
    return render(request, 'quiz/student/quiz_list.html', context)


@login_required
def quiz_detail(request, quiz_id):
    """Détails d'un quiz avant de le commencer"""
    quiz = get_object_or_404(Quiz, id=quiz_id, is_published=True)
    
    # Vérifier que l'étudiant a accès à ce quiz
    if not quiz.is_available_for_student(request.user):
        messages.error(request, "Vous n'avez pas accès à ce quiz.")
        return redirect('quiz:student_quiz_list')
    
    # Récupérer les tentatives de l'étudiant
    attempts = QuizAttempt.objects.filter(
        quiz=quiz, 
        user=request.user
    ).order_by('-started_at')
    
    # Vérifier si l'étudiant peut encore tenter le quiz
    can_attempt = attempts.count() < quiz.max_attempts
    has_active_attempt = attempts.filter(status='in_progress').exists()
    
    # Statistiques du quiz
    total_attempts = QuizAttempt.objects.filter(quiz=quiz, status__in=['submitted', 'graded']).count()
    avg_score = QuizAttempt.objects.filter(
        quiz=quiz, 
        status__in=['submitted', 'graded'],
        score__isnull=False
    ).aggregate(avg=Avg('score'))['avg'] or 0
    
    context = {
        'quiz': quiz,
        'attempts': attempts[:5],  # Dernières 5 tentatives
        'can_attempt': can_attempt,
        'has_active_attempt': has_active_attempt,
        'total_attempts': total_attempts,
        'average_score': avg_score,
        'questions_count': quiz.questions.count(),
        'total_points': quiz.total_points,
    }
    
    return render(request, 'quiz/student/quiz_detail.html', context)


@login_required
@require_POST
def quiz_start(request, quiz_id):
    """Démarrer une nouvelle tentative de quiz"""
    quiz = get_object_or_404(Quiz, id=quiz_id, is_published=True)
    
    # Vérifications de sécurité
    if not quiz.is_available_for_student(request.user):
        return JsonResponse({'error': 'Accès non autorisé'}, status=403)
    
    # Vérifier s'il y a déjà une tentative en cours
    active_attempt = QuizAttempt.objects.filter(
        quiz=quiz, 
        user=request.user, 
        status='in_progress'
    ).first()
    
    if active_attempt:
        return JsonResponse({
            'success': True,
            'attempt_id': str(active_attempt.id),
            'redirect_url': reverse('quiz:student_quiz_take', args=[active_attempt.id])
        })
    
    # Vérifier le nombre de tentatives
    attempts_count = QuizAttempt.objects.filter(quiz=quiz, user=request.user).count()
    if attempts_count >= quiz.max_attempts:
        return JsonResponse({'error': 'Nombre maximum de tentatives atteint'}, status=400)
    
    # Créer une nouvelle tentative
    with transaction.atomic():
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            user=request.user,
            attempt_number=attempts_count + 1,
            started_at=timezone.now(),
            status='in_progress'
        )
        
        # Calculer la date d'expiration si le quiz a une limite de temps
        if quiz.time_limit:
            attempt.expires_at = attempt.started_at + timedelta(minutes=quiz.time_limit)
            attempt.save()
    
    return JsonResponse({
        'success': True,
        'attempt_id': str(attempt.id),
        'redirect_url': reverse('quiz:student_quiz_take', args=[attempt.id])
    })


@login_required
def quiz_take(request, attempt_id):
    """Interface principale pour passer le quiz"""
    attempt = get_object_or_404(
        QuizAttempt, 
        id=attempt_id, 
        user=request.user,
        status='in_progress'
    )
    
    quiz = attempt.quiz
    
    # Vérifier l'expiration
    if attempt.is_expired():
        attempt.status = 'expired'
        attempt.submitted_at = timezone.now()
        attempt.save()
        messages.warning(request, "Le temps imparti pour ce quiz est écoulé.")
        return redirect('quiz:student_quiz_results', attempt_id=attempt.id)
    
    # Récupérer les questions
    questions = quiz.questions.prefetch_related('choices').order_by('order')
    
    # Mélanger les questions si configuré
    if quiz.randomize_questions:
        questions = list(questions)
        import random
        random.shuffle(questions)
    
    # Récupérer les réponses déjà données
    existing_answers = {}
    for answer in Answer.objects.filter(attempt=attempt):
        existing_answers[str(answer.question_id)] = answer.answer_data
    
    # Préparer les données des questions
    questions_data = []
    for i, question in enumerate(questions):
        choices_data = []
        if question.question_type in ['multiple_choice', 'single_choice', 'true_false']:
            choices = list(question.choices.all())
            if quiz.randomize_answers:
                import random
                random.shuffle(choices)
            
            for choice in choices:
                choices_data.append({
                    'id': choice.id,
                    'text': choice.choice_text,
                    'order': choice.order
                })
        
        questions_data.append({
            'id': question.id,
            'number': i + 1,
            'text': question.question_text,
            'type': question.question_type,
            'points': question.points,
            'image': question.image.url if question.image else None,
            'choices': choices_data,
            'existing_answer': existing_answers.get(str(question.id))
        })
    
    # Calculer le temps restant
    time_remaining = None
    if attempt.expires_at:
        time_remaining = max(0, int((attempt.expires_at - timezone.now()).total_seconds()))
    
    context = {
        'attempt': attempt,
        'quiz': quiz,
        'questions': questions_data,
        'time_remaining': time_remaining,
        'auto_save_interval': 30,  # Sauvegarde automatique toutes les 30 secondes
    }
    
    return render(request, 'quiz/student/quiz_take.html', context)


@login_required
@require_POST
@csrf_exempt
def quiz_save_answer(request, attempt_id):
    """Sauvegarder une réponse (AJAX)"""
    attempt = get_object_or_404(
        QuizAttempt, 
        id=attempt_id, 
        user=request.user,
        status='in_progress'
    )
    
    # Vérifier l'expiration
    if attempt.is_expired():
        return JsonResponse({'error': 'Quiz expiré'}, status=400)
    
    try:
        data = json.loads(request.body)
        question_id = data.get('question_id')
        answer_data = data.get('answer_data')
        
        question = get_object_or_404(Question, id=question_id, quiz=attempt.quiz)
        
        # Sauvegarder ou mettre à jour la réponse
        answer, created = Answer.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={
                'answer_data': answer_data,
                'answered_at': timezone.now()
            }
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Réponse sauvegardée',
            'question_id': question_id
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_POST
def quiz_submit(request, attempt_id):
    """Soumettre le quiz complet"""
    attempt = get_object_or_404(
        QuizAttempt, 
        id=attempt_id, 
        user=request.user,
        status='in_progress'
    )
    
    quiz = attempt.quiz
    
    with transaction.atomic():
        # Marquer comme soumis
        attempt.status = 'submitted'
        attempt.submitted_at = timezone.now()
        
        # Calculer le temps pris
        if attempt.started_at:
            attempt.time_taken = attempt.submitted_at - attempt.started_at
        
        # Calculer le score automatiquement
        total_points = 0
        earned_points = 0
        
        for question in quiz.questions.all():
            total_points += question.points
            
            try:
                answer = Answer.objects.get(attempt=attempt, question=question)
                if question.check_answer(answer.answer_data):
                    earned_points += question.points
                    answer.is_correct = True
                    answer.points_earned = question.points
                else:
                    answer.is_correct = False
                    answer.points_earned = 0
                answer.save()
                
            except Answer.DoesNotExist:
                # Question non répondue
                Answer.objects.create(
                    attempt=attempt,
                    question=question,
                    answer_data=None,
                    is_correct=False,
                    points_earned=0,
                    answered_at=attempt.submitted_at
                )
        
        # Calculer le score en pourcentage
        if total_points > 0:
            attempt.score = (earned_points / total_points) * 100
            attempt.passed = attempt.score >= quiz.passing_score
        else:
            attempt.score = 0
            attempt.passed = False
        
        attempt.save()
    
    # Rediriger vers les résultats
    return JsonResponse({
        'success': True,
        'redirect_url': reverse('quiz:student_quiz_results', args=[attempt.id])
    })


@login_required
def quiz_results(request, attempt_id):
    """Afficher les résultats du quiz"""
    attempt = get_object_or_404(
        QuizAttempt, 
        id=attempt_id, 
        user=request.user,
        status__in=['submitted', 'graded', 'expired']
    )
    
    quiz = attempt.quiz
    
    # Récupérer toutes les réponses avec les questions
    answers = Answer.objects.filter(attempt=attempt).select_related('question').order_by('question__order')
    
    # Organiser les données pour l'affichage
    results_data = []
    for answer in answers:
        question = answer.question
        
        # Préparer les choix avec indication des bonnes réponses
        choices_data = []
        if question.question_type in ['multiple_choice', 'single_choice', 'true_false']:
            for choice in question.choices.all():
                user_selected = False
                
                if answer.answer_data and isinstance(answer.answer_data, list):
                    user_selected = choice.id in answer.answer_data
                elif answer.answer_data and isinstance(answer.answer_data, (int, str)):
                    user_selected = choice.id == int(answer.answer_data)
                
                choices_data.append({
                    'choice': choice,
                    'user_selected': user_selected,
                    'is_correct': choice.is_correct
                })
        
        results_data.append({
            'question': question,
            'answer': answer,
            'choices': choices_data,
            'user_answer_text': answer.get_formatted_answer() if hasattr(answer, 'get_formatted_answer') else str(answer.answer_data) if answer.answer_data else 'Non répondu'
        })
    
    # Statistiques de la tentative
    total_questions = quiz.questions.count()
    answered_questions = answers.filter(answer_data__isnull=False).count()
    correct_answers = answers.filter(is_correct=True).count()
    
    # Comparaison avec les autres tentatives
    user_attempts = QuizAttempt.objects.filter(
        quiz=quiz, 
        user=request.user,
        status__in=['submitted', 'graded']
    ).order_by('-started_at')
    
    context = {
        'attempt': attempt,
        'quiz': quiz,
        'results_data': results_data,
        'total_questions': total_questions,
        'answered_questions': answered_questions,
        'correct_answers': correct_answers,
        'user_attempts': user_attempts,
        'show_corrections': quiz.show_correct_answers,
        'can_retake': user_attempts.count() < quiz.max_attempts,
    }
    
    return render(request, 'quiz/student/quiz_results.html', context)


@login_required
def quiz_review(request, attempt_id):
    """Révision détaillée des réponses avec explications"""
    attempt = get_object_or_404(
        QuizAttempt, 
        id=attempt_id, 
        user=request.user,
        status__in=['submitted', 'graded']
    )
    
    quiz = attempt.quiz
    
    # Vérifier si les corrections sont autorisées
    if not quiz.show_correct_answers:
        messages.error(request, "La révision des réponses n'est pas autorisée pour ce quiz.")
        return redirect('quiz:student_quiz_results', attempt_id=attempt.id)
    
    # Récupérer toutes les réponses avec détails
    answers = Answer.objects.filter(attempt=attempt).select_related('question').order_by('question__order')
    
    # Préparer les données détaillées pour la révision
    review_data = []
    for answer in answers:
        question = answer.question
        
        # Données spécifiques selon le type de question
        question_data = {
            'question': question,
            'answer': answer,
            'explanation': question.explanation,
        }
        
        if question.question_type in ['multiple_choice', 'single_choice', 'true_false']:
            choices_with_details = []
            for choice in question.choices.all():
                user_selected = False
                
                if answer.answer_data and isinstance(answer.answer_data, list):
                    user_selected = choice.id in answer.answer_data
                elif answer.answer_data and isinstance(answer.answer_data, (int, str)):
                    user_selected = choice.id == int(answer.answer_data)
                
                choices_with_details.append({
                    'choice': choice,
                    'user_selected': user_selected,
                    'is_correct': choice.is_correct,
                    'explanation': choice.explanation,
                    'should_be_selected': choice.is_correct
                })
            
            question_data['choices'] = choices_with_details
        
        elif question.question_type in ['short_answer', 'numerical']:
            correct_answers = []
            if question.question_type == 'short_answer' and question.correct_text:
                correct_answers = question.correct_text.split('\n')
            elif question.question_type == 'numerical' and question.correct_number is not None:
                correct_answers = [str(question.correct_number)]
                if question.tolerance:
                    min_val = question.correct_number - question.tolerance
                    max_val = question.correct_number + question.tolerance
                    correct_answers.append(f"Valeurs acceptées: {min_val} à {max_val}")
            
            question_data['correct_answers'] = correct_answers
            question_data['user_answer'] = answer.answer_data
        
        review_data.append(question_data)
    
    context = {
        'attempt': attempt,
        'quiz': quiz,
        'review_data': review_data,
    }
    
    return render(request, 'quiz/student/quiz_review.html', context)


@login_required
@require_POST
def quiz_resume(request, attempt_id):
    """Reprendre un quiz en cours"""
    attempt = get_object_or_404(
        QuizAttempt, 
        id=attempt_id, 
        user=request.user,
        status='in_progress'
    )
    
    # Vérifier l'expiration
    if attempt.is_expired():
        attempt.status = 'expired'
        attempt.submitted_at = timezone.now()
        attempt.save()
        return JsonResponse({'error': 'Quiz expiré'}, status=400)
    
    return JsonResponse({
        'success': True,
        'redirect_url': reverse('quiz:student_quiz_take', args=[attempt.id])
    })