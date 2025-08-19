from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction, models
from django.core.paginator import Paginator
from django.urls import reverse
from django.utils import timezone
import json

from core.permissions import instructor_required
from .models import Quiz, Question, Choice, QuizAttempt
from .forms import (
    QuizForm, QuestionForm, ChoiceForm, ChoiceFormSet,
    QuizPreviewForm, QuizDuplicateForm, QuestionImportForm,
    QuizAnalyticsFilterForm
)
from courses.models import Course, Lesson


# === GESTION DES QUIZ ===

@instructor_required
def quiz_list(request):
    """Liste des quiz de l'instructeur"""
    quiz_queryset = Quiz.objects.filter(instructor=request.user).select_related('course')
    
    # Filtres
    search = request.GET.get('search', '')
    course_id = request.GET.get('course', '')
    quiz_type = request.GET.get('quiz_type', '')
    is_published = request.GET.get('is_published', '')
    
    if search:
        quiz_queryset = quiz_queryset.filter(
            title__icontains=search
        )
    
    if course_id:
        quiz_queryset = quiz_queryset.filter(course_id=course_id)
    
    if quiz_type:
        quiz_queryset = quiz_queryset.filter(quiz_type=quiz_type)
    
    if is_published:
        quiz_queryset = quiz_queryset.filter(is_published=is_published == 'true')
    
    # Pagination
    paginator = Paginator(quiz_queryset, 12)
    page_number = request.GET.get('page')
    quizzes = paginator.get_page(page_number)
    
    # Données pour les filtres
    user_courses = Course.objects.filter(instructor=request.user)
    
    context = {
        'quizzes': quizzes,
        'user_courses': user_courses,
        'search': search,
        'current_course': course_id,
        'current_quiz_type': quiz_type,
        'current_is_published': is_published,
        'quiz_type_choices': Quiz.QUIZ_TYPES,
    }
    
    return render(request, 'quiz/instructor/quiz_list.html', context)


@instructor_required
def quiz_create(request):
    """Créer un nouveau quiz"""
    if request.method == 'POST':
        form = QuizForm(request.POST, user=request.user)
        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.instructor = request.user
            quiz.save()
            
            messages.success(request, f'Quiz "{quiz.title}" créé avec succès !')
            return redirect('quiz:quiz_detail', pk=quiz.pk)
    else:
        form = QuizForm(user=request.user)
    
    context = {
        'form': form,
        'page_title': 'Nouveau Quiz'
    }
    return render(request, 'quiz/instructor/quiz_form.html', context)


@instructor_required
def quiz_detail(request, pk):
    """Détails d'un quiz"""
    quiz = get_object_or_404(Quiz, pk=pk, instructor=request.user)
    questions = quiz.questions.all().order_by('order', 'id')
    
    # Statistiques du quiz
    attempts = quiz.attempts.filter(status__in=['submitted', 'graded'])
    stats = {
        'total_questions': quiz.total_questions,
        'total_points': quiz.total_points,
        'total_attempts': attempts.count(),
        'average_score': 0,
        'pass_rate': 0,
        'last_attempt': None,
    }
    
    if attempts.exists():
        scores = [a.score for a in attempts if a.score is not None]
        if scores:
            stats['average_score'] = round(sum(scores) / len(scores), 1)
            passed_count = len([s for s in scores if s >= quiz.passing_score])
            stats['pass_rate'] = round(passed_count / len(scores) * 100, 1)
        stats['last_attempt'] = attempts.order_by('-started_at').first()
    
    context = {
        'quiz': quiz,
        'questions': questions,
        'stats': stats,
    }
    return render(request, 'quiz/instructor/quiz_detail.html', context)


@instructor_required
def quiz_edit(request, pk):
    """Modifier un quiz"""
    quiz = get_object_or_404(Quiz, pk=pk, instructor=request.user)
    
    if request.method == 'POST':
        form = QuizForm(request.POST, instance=quiz, user=request.user)
        if form.is_valid():
            quiz = form.save()
            messages.success(request, f'Quiz "{quiz.title}" modifié avec succès !')
            return redirect('quiz:quiz_detail', pk=quiz.pk)
    else:
        form = QuizForm(instance=quiz, user=request.user)
    
    context = {
        'form': form,
        'quiz': quiz,
        'page_title': f'Modifier - {quiz.title}'
    }
    return render(request, 'quiz/instructor/quiz_form.html', context)


@instructor_required
@require_POST
def quiz_delete(request, pk):
    """Supprimer un quiz"""
    quiz = get_object_or_404(Quiz, pk=pk, instructor=request.user)
    title = quiz.title
    quiz.delete()
    
    messages.success(request, f'Quiz "{title}" supprimé.')
    return redirect('quiz:quiz_list')


@instructor_required
@require_POST
def quiz_duplicate(request, pk):
    """Dupliquer un quiz"""
    original_quiz = get_object_or_404(Quiz, pk=pk, instructor=request.user)
    
    if request.method == 'POST':
        form = QuizDuplicateForm(request.POST, user=request.user)
        if form.is_valid():
            # Dupliquer le quiz
            with transaction.atomic():
                new_quiz = Quiz.objects.create(
                    title=form.cleaned_data['new_title'],
                    description=original_quiz.description,
                    course=form.cleaned_data['new_course'] or original_quiz.course,
                    lesson=original_quiz.lesson,
                    instructor=request.user,
                    quiz_type=original_quiz.quiz_type,
                    difficulty=original_quiz.difficulty,
                    time_limit=original_quiz.time_limit,
                    max_attempts=original_quiz.max_attempts,
                    passing_score=original_quiz.passing_score,
                    randomize_questions=original_quiz.randomize_questions,
                    randomize_answers=original_quiz.randomize_answers,
                    show_correct_answers=original_quiz.show_correct_answers,
                    show_score_immediately=original_quiz.show_score_immediately,
                    is_published=False,  # Nouvelle copie non publiée
                    is_required=original_quiz.is_required,
                )
                
                # Dupliquer les questions si demandé
                if form.cleaned_data['copy_questions']:
                    for original_question in original_quiz.questions.all():
                        new_question = Question.objects.create(
                            quiz=new_quiz,
                            question_text=original_question.question_text,
                            question_type=original_question.question_type,
                            points=original_question.points,
                            order=original_question.order,
                            explanation=original_question.explanation,
                            correct_number=original_question.correct_number,
                            tolerance=original_question.tolerance,
                            correct_text=original_question.correct_text,
                            case_sensitive=original_question.case_sensitive,
                        )
                        
                        # Dupliquer les choix
                        for original_choice in original_question.choices.all():
                            Choice.objects.create(
                                question=new_question,
                                choice_text=original_choice.choice_text,
                                is_correct=original_choice.is_correct,
                                order=original_choice.order,
                                explanation=original_choice.explanation,
                            )
            
            messages.success(request, f'Quiz dupliqué vers "{new_quiz.title}"')
            return redirect('quiz:quiz_detail', pk=new_quiz.pk)
    
    return redirect('quiz:quiz_detail', pk=pk)


@instructor_required
@require_POST
def quiz_publish(request, pk):
    """Publier/dépublier un quiz"""
    quiz = get_object_or_404(Quiz, pk=pk, instructor=request.user)
    
    # Vérifications avant publication
    if not quiz.is_published:
        if not quiz.questions.exists():
            messages.error(request, 'Impossible de publier : le quiz doit avoir au moins une question.')
            return redirect('quiz:quiz_detail', pk=quiz.pk)
        
        # Vérifier que toutes les questions ont des réponses correctes
        for question in quiz.questions.all():
            if question.question_type in ['multiple_choice', 'single_choice', 'true_false']:
                if not question.choices.filter(is_correct=True).exists():
                    messages.error(request, f'Question "{question.question_text[:30]}..." n\'a pas de réponse correcte définie.')
                    return redirect('quiz:quiz_detail', pk=quiz.pk)
    
    quiz.is_published = not quiz.is_published
    quiz.save()
    
    action = "publié" if quiz.is_published else "dépublié"
    messages.success(request, f'Quiz "{quiz.title}" {action} avec succès.')
    return redirect('quiz:quiz_detail', pk=quiz.pk)


# === GESTION DES QUESTIONS ===

@instructor_required
def question_create(request, quiz_pk):
    """Créer une nouvelle question"""
    quiz = get_object_or_404(Quiz, pk=quiz_pk, instructor=request.user)
    
    if request.method == 'POST':
        form = QuestionForm(request.POST, request.FILES)
        if form.is_valid():
            question = form.save(commit=False)
            question.quiz = quiz
            
            # Auto-assign order if not specified
            if not question.order:
                max_order = quiz.questions.aggregate(
                    models.Max('order'))['order__max'] or 0
                question.order = max_order + 1
            
            question.save()
            
            messages.success(request, 'Question créée avec succès !')
            
            # Rediriger selon le type de question
            if question.question_type in ['multiple_choice', 'single_choice', 'true_false']:
                return redirect('quiz:question_edit_choices', quiz_pk=quiz.pk, pk=question.pk)
            else:
                return redirect('quiz:quiz_detail', pk=quiz.pk)
    else:
        # Pre-fill next order
        max_order = quiz.questions.aggregate(
            models.Max('order'))['order__max'] or 0
        form = QuestionForm(initial={'order': max_order + 1})
    
    context = {
        'form': form,
        'quiz': quiz,
        'page_title': f'Nouvelle Question - {quiz.title}'
    }
    return render(request, 'quiz/instructor/question_form.html', context)


@instructor_required
def question_edit(request, quiz_pk, pk):
    """Modifier une question"""
    quiz = get_object_or_404(Quiz, pk=quiz_pk, instructor=request.user)
    question = get_object_or_404(Question, pk=pk, quiz=quiz)
    
    if request.method == 'POST':
        form = QuestionForm(request.POST, request.FILES, instance=question)
        if form.is_valid():
            question = form.save()
            messages.success(request, 'Question modifiée avec succès !')
            return redirect('quiz:quiz_detail', pk=quiz.pk)
    else:
        form = QuestionForm(instance=question)
    
    context = {
        'form': form,
        'quiz': quiz,
        'question': question,
        'page_title': f'Modifier Question - {quiz.title}'
    }
    return render(request, 'quiz/instructor/question_form.html', context)


@instructor_required
def question_edit_choices(request, quiz_pk, pk):
    """Modifier les choix d'une question QCM/QCU/Vrai-Faux"""
    quiz = get_object_or_404(Quiz, pk=quiz_pk, instructor=request.user)
    question = get_object_or_404(Question, pk=pk, quiz=quiz)
    
    if question.question_type not in ['multiple_choice', 'single_choice', 'true_false']:
        messages.error(request, 'Cette question ne nécessite pas de choix de réponse.')
        return redirect('quiz:quiz_detail', pk=quiz.pk)
    
    if request.method == 'POST':
        formset = ChoiceFormSet(request.POST, instance=question)
        if formset.is_valid():
            formset.save()
            messages.success(request, 'Choix de réponse sauvegardés !')
            return redirect('quiz:quiz_detail', pk=quiz.pk)
    else:
        formset = ChoiceFormSet(instance=question)
    
    context = {
        'quiz': quiz,
        'question': question,
        'formset': formset,
        'page_title': f'Choix de Réponse - {question.question_text[:50]}...'
    }
    return render(request, 'quiz/instructor/question_choices.html', context)


@instructor_required
@require_POST
def question_delete(request, quiz_pk, pk):
    """Supprimer une question"""
    quiz = get_object_or_404(Quiz, pk=quiz_pk, instructor=request.user)
    question = get_object_or_404(Question, pk=pk, quiz=quiz)
    
    question.delete()
    messages.success(request, 'Question supprimée.')
    return redirect('quiz:quiz_detail', pk=quiz.pk)


# === PRÉVISUALISATION ===

@instructor_required
def quiz_preview(request, pk):
    """Prévisualiser un quiz"""
    quiz = get_object_or_404(Quiz, pk=pk, instructor=request.user)
    
    # Configuration de la prévisualisation
    show_answers = request.GET.get('show_answers', 'true') == 'true'
    show_explanations = request.GET.get('show_explanations', 'true') == 'true'
    randomize_preview = request.GET.get('randomize_preview', 'false') == 'true'
    
    questions = quiz.questions.all().order_by('order')
    
    if randomize_preview and quiz.randomize_questions:
        questions = questions.order_by('?')
    
    context = {
        'quiz': quiz,
        'questions': questions,
        'show_answers': show_answers,
        'show_explanations': show_explanations,
        'randomize_preview': randomize_preview,
        'is_preview': True,
    }
    return render(request, 'quiz/instructor/quiz_preview.html', context)


# === ANALYTICS ET STATISTIQUES ===

@instructor_required
def quiz_analytics(request, pk):
    """Analytics détaillées du quiz"""
    quiz = get_object_or_404(Quiz, pk=pk, instructor=request.user)
    
    # Filtres
    form = QuizAnalyticsFilterForm(request.GET)
    attempts = quiz.attempts.filter(status__in=['submitted', 'graded'])
    
    if form.is_valid():
        if form.cleaned_data['date_from']:
            attempts = attempts.filter(started_at__date__gte=form.cleaned_data['date_from'])
        if form.cleaned_data['date_to']:
            attempts = attempts.filter(started_at__date__lte=form.cleaned_data['date_to'])
        if form.cleaned_data['status']:
            attempts = attempts.filter(status=form.cleaned_data['status'])
        if form.cleaned_data['passed']:
            passed_bool = form.cleaned_data['passed'] == 'true'
            attempts = attempts.filter(passed=passed_bool)
    
    # Statistiques générales
    stats = {
        'total_attempts': attempts.count(),
        'unique_users': attempts.values('user').distinct().count(),
        'average_score': 0,
        'median_score': 0,
        'pass_rate': 0,
        'average_time': None,
        'score_distribution': {},
        'question_stats': [],
    }
    
    if attempts.exists():
        scores = [a.score for a in attempts if a.score is not None]
        
        if scores:
            stats['average_score'] = round(sum(scores) / len(scores), 1)
            scores.sort()
            n = len(scores)
            stats['median_score'] = scores[n//2] if n % 2 == 1 else (scores[n//2-1] + scores[n//2]) / 2
            
            passed_count = len([s for s in scores if s >= quiz.passing_score])
            stats['pass_rate'] = round(passed_count / len(scores) * 100, 1)
            
            # Distribution des scores
            for score in scores:
                range_key = f"{int(score//10)*10}-{int(score//10)*10+9}"
                stats['score_distribution'][range_key] = stats['score_distribution'].get(range_key, 0) + 1
        
        # Temps moyen
        times = [a.time_taken for a in attempts if a.time_taken]
        if times:
            avg_seconds = sum(t.total_seconds() for t in times) / len(times)
            stats['average_time'] = int(avg_seconds)
        
        # Statistiques par question
        for question in quiz.questions.all():
            correct_count = 0
            total_responses = 0
            
            for attempt in attempts:
                answers_data = attempt.get_answers_data()
                question_id = str(question.id)
                
                if question_id in answers_data:
                    total_responses += 1
                    user_answer = answers_data[question_id]
                    if question.check_answer(user_answer):
                        correct_count += 1
            
            success_rate = (correct_count / total_responses * 100) if total_responses > 0 else 0
            
            stats['question_stats'].append({
                'question': question,
                'success_rate': round(success_rate, 1),
                'total_responses': total_responses,
                'difficulty_level': 'Facile' if success_rate >= 80 else 'Moyenne' if success_rate >= 60 else 'Difficile'
            })
    
    context = {
        'quiz': quiz,
        'stats': stats,
        'form': form,
        'recent_attempts': attempts.select_related('user').order_by('-started_at')[:10]
    }
    
    return render(request, 'quiz/instructor/quiz_analytics.html', context)


# === AJAX ENDPOINTS ===

@instructor_required
def get_lessons_by_course(request):
    """AJAX: Récupère les leçons d'un cours"""
    course_id = request.GET.get('course_id')
    lessons = []
    
    if course_id:
        try:
            course = Course.objects.get(id=course_id, instructor=request.user)
            lessons = list(course.lessons.values('id', 'title'))
        except Course.DoesNotExist:
            pass
    
    return JsonResponse({'lessons': lessons})


@instructor_required
def get_questions_by_quiz(request):
    """AJAX: Récupère les questions d'un quiz"""
    quiz_id = request.GET.get('quiz_id')
    questions = []
    
    if quiz_id:
        try:
            quiz = Quiz.objects.get(id=quiz_id, instructor=request.user)
            questions = list(quiz.questions.values('id', 'question_text', 'question_type', 'points'))
        except Quiz.DoesNotExist:
            pass
    
    return JsonResponse({'questions': questions})


@instructor_required
@require_POST
def reorder_questions(request, quiz_pk):
    """AJAX: Réorganise l'ordre des questions"""
    quiz = get_object_or_404(Quiz, pk=quiz_pk, instructor=request.user)
    
    try:
        question_orders = json.loads(request.body)
        
        with transaction.atomic():
            for item in question_orders:
                Question.objects.filter(
                    id=item['id'], 
                    quiz=quiz
                ).update(order=item['order'])
        
        return JsonResponse({'success': True, 'message': 'Ordre mis à jour'})
    
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        return JsonResponse({'success': False, 'error': str(e)})


@instructor_required
def question_quick_edit(request, quiz_pk, pk):
    """AJAX: Édition rapide d'une question"""
    quiz = get_object_or_404(Quiz, pk=quiz_pk, instructor=request.user)
    question = get_object_or_404(Question, pk=pk, quiz=quiz)
    
    if request.method == 'POST':
        field = request.POST.get('field')
        value = request.POST.get('value')
        
        allowed_fields = ['question_text', 'points', 'explanation']
        
        if field in allowed_fields:
            setattr(question, field, value)
            question.save()
            return JsonResponse({'success': True, 'message': 'Question mise à jour'})
    
    return JsonResponse({'success': False, 'error': 'Modification non autorisée'})