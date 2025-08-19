from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.conf import settings
from django.db import models
import json
import os

from core.permissions import instructor_required
from .models import Course, Category, Tag, Module, Lesson, LessonResource, Enrollment
from .forms import CourseForm, ModuleForm, LessonForm, LessonResourceForm


@instructor_required
def courses_management(request):
    """Liste et gestion des cours de l'instructeur"""
    courses = Course.objects.filter(instructor=request.user).select_related('category').order_by('-updated_at')
    
    context = {
        'courses': courses,
        'page_title': 'Mes Cours'
    }
    return render(request, 'instructor/courses_list.html', context)


@instructor_required
def course_create(request):
    """Créer un nouveau cours"""
    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES)
        if form.is_valid():
            course = form.save(commit=False)
            course.instructor = request.user
            course.save()
            form.save_m2m()  # Pour les tags
            
            messages.success(request, f'Cours "{course.title}" créé avec succès !')
            return redirect('instructor:course_detail', pk=course.pk)
    else:
        form = CourseForm()
    
    context = {
        'form': form,
        'page_title': 'Créer un Cours',
        'categories': Category.objects.filter(is_active=True).order_by('name'),
        'tags': Tag.objects.all().order_by('name')
    }
    return render(request, 'instructor/course_form.html', context)


@instructor_required
def course_edit(request, pk):
    """Modifier un cours"""
    course = get_object_or_404(Course, pk=pk, instructor=request.user)
    
    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES, instance=course)
        if form.is_valid():
            course = form.save()
            messages.success(request, f'Cours "{course.title}" mis à jour avec succès !')
            return redirect('instructor:course_detail', pk=course.pk)
    else:
        form = CourseForm(instance=course)
    
    context = {
        'form': form,
        'course': course,
        'page_title': f'Modifier: {course.title}',
        'categories': Category.objects.filter(is_active=True).order_by('name'),
        'tags': Tag.objects.all().order_by('name')
    }
    return render(request, 'instructor/course_form.html', context)


@instructor_required
def course_detail(request, pk):
    """Détail et gestion d'un cours"""
    course = get_object_or_404(
        Course.objects.select_related('category', 'instructor')
        .prefetch_related('tags', 'modules__lessons'),
        pk=pk, 
        instructor=request.user
    )
    
    # Statistiques du cours
    enrollments = course.enrollments.all()
    total_students = enrollments.count()
    revenue = sum(e.amount_paid for e in enrollments)
    
    # Modules et leçons
    modules = course.modules.all().order_by('order')
    total_lessons = sum(module.lessons.count() for module in modules)
    
    context = {
        'course': course,
        'modules': modules,
        'stats': {
            'total_students': total_students,
            'revenue': revenue,
            'total_modules': modules.count(),
            'total_lessons': total_lessons,
        },
        'page_title': course.title
    }
    return render(request, 'instructor/course_detail.html', context)


@instructor_required
@require_POST
def course_publish(request, pk):
    """Publier un cours"""
    course = get_object_or_404(Course, pk=pk, instructor=request.user)
    
    # Vérifications détaillées avant publication
    total_modules = course.modules.count()
    published_modules = course.modules.filter(is_published=True).count()
    
    if total_modules == 0:
        messages.error(request, 'Impossible de publier : le cours doit avoir au moins un module.')
        return redirect('instructor:course_detail', pk=course.pk)
    
    if published_modules == 0:
        messages.error(request, 
            f'Impossible de publier : aucun des {total_modules} module(s) n\'est publié. '
            'Veuillez publier au moins un module en cochant "Module publié" dans ses paramètres.')
        return redirect('instructor:course_detail', pk=course.pk)
    
    # Vérifier qu'il y a du contenu publié
    has_published_content = False
    published_lessons_count = 0
    
    for module in course.modules.filter(is_published=True):
        module_lessons = module.lessons.filter(is_published=True).count()
        published_lessons_count += module_lessons
        if module_lessons > 0:
            has_published_content = True
    
    if not has_published_content:
        total_lessons = sum(m.lessons.count() for m in course.modules.all())
        messages.error(request, 
            f'Impossible de publier : aucune leçon n\'est publiée dans les modules publiés. '
            f'Vous avez {total_lessons} leçon(s) au total. '
            'Veuillez publier au moins une leçon en cochant "Leçon publiée" dans ses paramètres.')
        return redirect('instructor:course_detail', pk=course.pk)
    
    # Tout est OK, publier le cours
    course.status = 'published'
    course.save()
    
    messages.success(request, 
        f'Cours "{course.title}" publié avec succès ! '
        f'({published_modules} module(s) et {published_lessons_count} leçon(s) publiés)')
    return redirect('instructor:course_detail', pk=course.pk)


@instructor_required
@require_POST
def course_unpublish(request, pk):
    """Dépublier un cours"""
    course = get_object_or_404(Course, pk=pk, instructor=request.user)
    course.status = 'draft'
    course.save()
    
    messages.success(request, f'Cours "{course.title}" dépublié.')
    return redirect('instructor:course_detail', pk=course.pk)


@instructor_required
@require_POST
def course_delete(request, pk):
    """Supprimer un cours"""
    course = get_object_or_404(Course, pk=pk, instructor=request.user)
    title = course.title
    course.delete()
    
    messages.success(request, f'Cours "{title}" supprimé.')
    return redirect('instructor:courses')


# === GESTION DES MODULES ===

@instructor_required
def module_create(request, course_pk):
    """Créer un module"""
    course = get_object_or_404(Course, pk=course_pk, instructor=request.user)
    
    if request.method == 'POST':
        form = ModuleForm(request.POST)
        if form.is_valid():
            module = form.save(commit=False)
            module.course = course
            
            # Auto-assign the next order if not specified or if there's a conflict
            if not module.order or course.modules.filter(order=module.order).exists():
                max_order = course.modules.aggregate(
                    models.Max('order'))['order__max'] or 0
                module.order = max_order + 1
            
            module.save()
            
            messages.success(request, f'Module "{module.title}" créé avec succès !')
            return redirect('instructor:course_detail', pk=course.pk)
    else:
        # Pre-fill the next order number and publish by default
        max_order = course.modules.aggregate(
            models.Max('order'))['order__max'] or 0
        form = ModuleForm(initial={'order': max_order + 1, 'is_published': True})
    
    context = {
        'form': form,
        'course': course,
        'page_title': f'Nouveau Module - {course.title}'
    }
    return render(request, 'instructor/module_form.html', context)


@instructor_required
def module_edit(request, course_pk, pk):
    """Modifier un module"""
    course = get_object_or_404(Course, pk=course_pk, instructor=request.user)
    module = get_object_or_404(Module, pk=pk, course=course)
    
    if request.method == 'POST':
        form = ModuleForm(request.POST, instance=module)
        if form.is_valid():
            module = form.save()
            messages.success(request, f'Module "{module.title}" mis à jour !')
            return redirect('instructor:course_detail', pk=course.pk)
    else:
        form = ModuleForm(instance=module)
    
    context = {
        'form': form,
        'course': course,
        'module': module,
        'page_title': f'Modifier Module - {module.title}'
    }
    return render(request, 'instructor/module_form.html', context)


@instructor_required
@require_POST
def module_delete(request, course_pk, pk):
    """Supprimer un module"""
    course = get_object_or_404(Course, pk=course_pk, instructor=request.user)
    module = get_object_or_404(Module, pk=pk, course=course)
    title = module.title
    module.delete()
    
    messages.success(request, f'Module "{title}" supprimé.')
    return redirect('instructor:course_detail', pk=course.pk)


@instructor_required
@require_POST
def module_publish(request, course_pk, pk):
    """Publier un module"""
    course = get_object_or_404(Course, pk=course_pk, instructor=request.user)
    module = get_object_or_404(Module, pk=pk, course=course)
    
    module.is_published = True
    module.save()
    
    messages.success(request, f'Module "{module.title}" publié avec succès !')
    return redirect('instructor:course_detail', pk=course.pk)


@instructor_required
@require_POST
def module_unpublish(request, course_pk, pk):
    """Dépublier un module"""
    course = get_object_or_404(Course, pk=course_pk, instructor=request.user)
    module = get_object_or_404(Module, pk=pk, course=course)
    
    module.is_published = False
    module.save()
    
    messages.success(request, f'Module "{module.title}" dépublié.')
    return redirect('instructor:course_detail', pk=course.pk)


# === GESTION DES LEÇONS ===

@instructor_required
def lesson_create(request, course_pk, module_pk):
    """Créer une leçon"""
    course = get_object_or_404(Course, pk=course_pk, instructor=request.user)
    module = get_object_or_404(Module, pk=module_pk, course=course)
    
    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.module = module
            
            # Auto-assign the next order if not specified or if there's a conflict
            if not lesson.order or module.lessons.filter(order=lesson.order).exists():
                max_order = module.lessons.aggregate(
                    models.Max('order'))['order__max'] or 0
                lesson.order = max_order + 1
            
            lesson.save()
            
            messages.success(request, f'Leçon "{lesson.title}" créée avec succès !')
            return redirect('instructor:lesson_detail', 
                          course_pk=course.pk, module_pk=module.pk, pk=lesson.pk)
    else:
        # Pre-fill the next order number and publish by default
        max_order = module.lessons.aggregate(
            models.Max('order'))['order__max'] or 0
        form = LessonForm(initial={'order': max_order + 1, 'is_published': True})
    
    context = {
        'form': form,
        'course': course,
        'module': module,
        'page_title': f'Nouvelle Leçon - {module.title}'
    }
    return render(request, 'instructor/lesson_form.html', context)


@instructor_required
def lesson_detail(request, course_pk, module_pk, pk):
    """Détail d'une leçon avec gestion des ressources"""
    course = get_object_or_404(Course, pk=course_pk, instructor=request.user)
    module = get_object_or_404(Module, pk=module_pk, course=course)
    lesson = get_object_or_404(Lesson, pk=pk, module=module)
    
    resources = lesson.resources.all().order_by('order')
    
    context = {
        'course': course,
        'module': module,
        'lesson': lesson,
        'resources': resources,
        'page_title': f'{lesson.title} - {module.title}'
    }
    return render(request, 'instructor/lesson_detail.html', context)


@instructor_required
def lesson_edit(request, course_pk, module_pk, pk):
    """Modifier une leçon"""
    course = get_object_or_404(Course, pk=course_pk, instructor=request.user)
    module = get_object_or_404(Module, pk=module_pk, course=course)
    lesson = get_object_or_404(Lesson, pk=pk, module=module)
    
    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES, instance=lesson)
        if form.is_valid():
            lesson = form.save()
            messages.success(request, f'Leçon "{lesson.title}" mise à jour !')
            return redirect('instructor:lesson_detail', 
                          course_pk=course.pk, module_pk=module.pk, pk=lesson.pk)
    else:
        form = LessonForm(instance=lesson)
    
    context = {
        'form': form,
        'course': course,
        'module': module,
        'lesson': lesson,
        'page_title': f'Modifier - {lesson.title}'
    }
    return render(request, 'instructor/lesson_form.html', context)


@instructor_required
@require_POST
def lesson_publish(request, course_pk, module_pk, pk):
    """Publier une leçon"""
    course = get_object_or_404(Course, pk=course_pk, instructor=request.user)
    module = get_object_or_404(Module, pk=module_pk, course=course)
    lesson = get_object_or_404(Lesson, pk=pk, module=module)
    
    lesson.is_published = True
    lesson.save()
    
    messages.success(request, f'Leçon "{lesson.title}" publiée avec succès !')
    return redirect('instructor:lesson_detail', 
                   course_pk=course.pk, module_pk=module.pk, pk=lesson.pk)


@instructor_required
@require_POST
def lesson_unpublish(request, course_pk, module_pk, pk):
    """Dépublier une leçon"""
    course = get_object_or_404(Course, pk=course_pk, instructor=request.user)
    module = get_object_or_404(Module, pk=module_pk, course=course)
    lesson = get_object_or_404(Lesson, pk=pk, module=module)
    
    lesson.is_published = False
    lesson.save()
    
    messages.success(request, f'Leçon "{lesson.title}" dépubliée.')
    return redirect('instructor:lesson_detail', 
                   course_pk=course.pk, module_pk=module.pk, pk=lesson.pk)


@instructor_required  
@require_POST
def lesson_delete(request, course_pk, module_pk, pk):
    """Supprimer une leçon"""
    course = get_object_or_404(Course, pk=course_pk, instructor=request.user)
    module = get_object_or_404(Module, pk=module_pk, course=course)
    lesson = get_object_or_404(Lesson, pk=pk, module=module)
    
    title = lesson.title
    lesson.delete()
    
    messages.success(request, f'Leçon "{title}" supprimée.')
    return redirect('instructor:course_detail', pk=course.pk)


# === AJAX ENDPOINTS ===

@instructor_required
@require_http_methods(["POST"])
@csrf_exempt
def upload_media(request):
    """Upload AJAX pour fichiers multimédia"""
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'Aucun fichier fourni'}, status=400)
    
    file = request.FILES['file']
    file_type = request.POST.get('type', 'document')
    
    # Validation taille et type
    max_size = 100 * 1024 * 1024  # 100MB
    if file.size > max_size:
        return JsonResponse({'error': 'Fichier trop volumineux'}, status=400)
    
    # Déterminer le dossier selon le type
    folder_map = {
        'video': 'courses/videos/',
        'audio': 'courses/audio/', 
        'document': 'courses/documents/',
        'image': 'courses/images/'
    }
    
    folder = folder_map.get(file_type, 'courses/documents/')
    
    # Sauvegarder le fichier
    file_path = default_storage.save(f"{folder}{file.name}", file)
    file_url = default_storage.url(file_path)
    
    return JsonResponse({
        'success': True,
        'file_path': file_path,
        'file_url': file_url,
        'file_name': file.name,
        'file_size': file.size
    })


@instructor_required
def course_analytics(request, pk):
    """Analytics détaillées d'un cours"""
    course = get_object_or_404(Course, pk=pk, instructor=request.user)
    
    enrollments = course.enrollments.select_related('user')
    
    # Données pour les graphiques
    analytics_data = {
        'total_enrollments': enrollments.count(),
        'revenue': sum(e.amount_paid for e in enrollments),
        'completion_rate': 0,  # À calculer selon la logique métier
        'enrollments_by_month': {},  # À implémenter
        'student_progress': [],  # À implémenter
    }
    
    context = {
        'course': course,
        'enrollments': enrollments,
        'analytics': analytics_data,
        'page_title': f'Analytics - {course.title}'
    }
    return render(request, 'instructor/course_analytics.html', context)