from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg
from django.http import Http404, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Course, Category, Tag, Module, Lesson, Enrollment, CourseFavorite


def courses_list(request):
    """Liste tous les cours publiés avec filtres et recherche"""
    courses = Course.objects.filter(status='published').select_related(
        'category', 'instructor'
    ).prefetch_related('tags')
    
    # Recherche
    search_query = request.GET.get('search', '')
    if search_query:
        courses = courses.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(short_description__icontains=search_query) |
            Q(instructor__first_name__icontains=search_query) |
            Q(instructor__last_name__icontains=search_query)
        )
    
    # Filtrage par catégorie
    category_slug = request.GET.get('category')
    selected_category = None
    if category_slug:
        try:
            selected_category = Category.objects.get(slug=category_slug, is_active=True)
            courses = courses.filter(category=selected_category)
        except Category.DoesNotExist:
            pass
    
    # Filtrage par niveau de difficulté
    difficulty = request.GET.get('difficulty')
    if difficulty and difficulty in dict(Course.DIFFICULTY_CHOICES):
        courses = courses.filter(difficulty=difficulty)
    
    # Filtrage par prix (gratuit/payant)
    price_filter = request.GET.get('price')
    if price_filter == 'free':
        courses = courses.filter(is_free=True)
    elif price_filter == 'paid':
        courses = courses.filter(is_free=False)
    
    # Tri
    sort_by = request.GET.get('sort', '-created_at')
    valid_sorts = ['-created_at', 'created_at', 'title', '-title', '-enrollment_count', 'difficulty']
    if sort_by in valid_sorts:
        courses = courses.order_by(sort_by)
    else:
        courses = courses.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(courses, 12)  # 12 cours par page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Données pour les filtres
    categories = Category.objects.filter(is_active=True, courses__status='published').annotate(
        course_count=Count('courses', filter=Q(courses__status='published'))
    ).distinct()
    
    context = {
        'page_obj': page_obj,
        'courses': page_obj,
        'categories': categories,
        'selected_category': selected_category,
        'search_query': search_query,
        'difficulty_choices': Course.DIFFICULTY_CHOICES,
        'selected_difficulty': difficulty,
        'selected_price': price_filter,
        'selected_sort': sort_by,
        'total_courses': paginator.count,
    }
    
    return render(request, 'courses/courses_list.html', context)


def course_detail(request, slug):
    """Détail d'un cours avec ses modules et leçons"""
    course = get_object_or_404(
        Course.objects.select_related('category', 'instructor').prefetch_related(
            'tags', 'co_instructors', 
            'modules__lessons',
        ),
        slug=slug,
        status='published'
    )
    
    # Vérifier les permissions d'accès
    user = request.user
    can_access_full_content = False
    is_enrolled = False
    is_favorite = False
    enrollment = None
    
    if user.is_authenticated:
        # Vérifier si l'utilisateur est inscrit
        try:
            enrollment = Enrollment.objects.get(user=user, course=course, status='active')
            is_enrolled = True
            can_access_full_content = True
        except Enrollment.DoesNotExist:
            pass
        
        # Vérifier si le cours est en favoris
        is_favorite = CourseFavorite.objects.filter(user=user, course=course).exists()
        
        # Donner accès aux instructeurs et admins
        if user.is_instructor or user.is_admin or user == course.instructor:
            can_access_full_content = True
    
    # Modules et leçons
    modules = course.modules.filter(is_published=True).prefetch_related(
        'lessons'
    ).order_by('order')
    
    # Compter les leçons gratuites (preview)
    free_lessons_count = sum(
        module.lessons.filter(is_preview=True, is_published=True).count() 
        for module in modules
    )
    
    # Cours similaires (même catégorie)
    related_courses = Course.objects.filter(
        category=course.category,
        status='published'
    ).exclude(id=course.id).select_related('instructor')[:4]
    
    context = {
        'course': course,
        'modules': modules,
        'can_access_full_content': can_access_full_content,
        'is_enrolled': is_enrolled,
        'is_favorite': is_favorite,
        'enrollment': enrollment,
        'free_lessons_count': free_lessons_count,
        'related_courses': related_courses,
        'total_duration_hours': int(course.total_duration),
        'total_duration_minutes': int((course.total_duration % 1) * 60),
    }
    
    return render(request, 'courses/course_detail.html', context)


def lesson_detail(request, course_slug, lesson_id):
    """Affichage d'une leçon individuelle"""
    course = get_object_or_404(Course, slug=course_slug, status='published')
    lesson = get_object_or_404(
        Lesson.objects.select_related('module'),
        id=lesson_id,
        module__course=course,
        is_published=True
    )
    
    # Vérifier les permissions d'accès
    user = request.user
    can_access = False
    
    if lesson.is_preview:
        # Leçons gratuites accessibles à tous
        can_access = True
    elif user.is_authenticated:
        # Vérifier si l'utilisateur est inscrit ou est l'instructeur
        if user.is_instructor or user.is_admin or user == course.instructor:
            can_access = True
        # TODO: Vérifier l'inscription au cours
        # elif user.enrollments.filter(course=course).exists():
        #     can_access = True
    
    if not can_access:
        raise Http404("Vous n'avez pas accès à cette leçon.")
    
    # Navigation entre leçons
    module = lesson.module
    all_lessons = list(module.lessons.filter(is_published=True).order_by('order'))
    current_index = all_lessons.index(lesson)
    
    previous_lesson = all_lessons[current_index - 1] if current_index > 0 else None
    next_lesson = all_lessons[current_index + 1] if current_index < len(all_lessons) - 1 else None
    
    # Si pas de leçon suivante dans ce module, chercher dans le module suivant
    if not next_lesson:
        next_modules = course.modules.filter(
            order__gt=module.order, 
            is_published=True
        ).order_by('order')
        
        for next_module in next_modules:
            first_lesson = next_module.lessons.filter(is_published=True).order_by('order').first()
            if first_lesson:
                next_lesson = first_lesson
                break
    
    context = {
        'course': course,
        'lesson': lesson,
        'module': module,
        'previous_lesson': previous_lesson,
        'next_lesson': next_lesson,
        'lesson_number': current_index + 1,
        'total_lessons_in_module': len(all_lessons),
    }
    
    return render(request, 'courses/lesson_detail.html', context)


def categories_list(request):
    """Liste des catégories avec leurs cours"""
    categories = Category.objects.filter(
        is_active=True,
        courses__status='published'
    ).annotate(
        course_count=Count('courses', filter=Q(courses__status='published'))
    ).distinct().order_by('order', 'name')
    
    context = {
        'categories': categories,
    }
    
    return render(request, 'courses/categories_list.html', context)


def category_detail(request, slug):
    """Détail d'une catégorie avec ses cours"""
    category = get_object_or_404(Category, slug=slug, is_active=True)
    
    courses = Course.objects.filter(
        category=category,
        status='published'
    ).select_related('instructor').prefetch_related('tags')
    
    # Pagination
    paginator = Paginator(courses, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Sous-catégories
    subcategories = category.subcategories.filter(
        is_active=True,
        courses__status='published'
    ).annotate(
        course_count=Count('courses', filter=Q(courses__status='published'))
    ).distinct()
    
    context = {
        'category': category,
        'page_obj': page_obj,
        'courses': page_obj,
        'subcategories': subcategories,
        'total_courses': paginator.count,
    }
    
    return render(request, 'courses/category_detail.html', context)


@login_required
@require_POST
def enroll_course(request, slug):
    """Inscription à un cours"""
    course = get_object_or_404(Course, slug=slug, status='published')
    
    # Vérifier si l'utilisateur est déjà inscrit
    enrollment, created = Enrollment.objects.get_or_create(
        user=request.user,
        course=course,
        defaults={
            'started_at': timezone.now() if course.is_free else None,
            'amount_paid': 0.00 if course.is_free else course.price,
            'payment_date': timezone.now() if course.is_free else None,
        }
    )
    
    if created:
        if course.is_free:
            messages.success(
                request, 
                f"Vous êtes maintenant inscrit au cours '{course.title}' !"
            )
        else:
            messages.info(
                request,
                f"Inscription initiée pour '{course.title}'. Procédez au paiement pour accéder au contenu."
            )
        
        # Mettre à jour le compteur d'inscriptions
        course.enrollment_count += 1
        course.save()
    else:
        messages.info(request, "Vous êtes déjà inscrit à ce cours.")
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'enrolled': True,
            'message': "Inscription réussie !" if created else "Déjà inscrit"
        })
    
    return redirect('courses:course_detail', slug=course.slug)


@login_required
@require_POST
def toggle_favorite(request, slug):
    """Ajouter/retirer un cours des favoris"""
    course = get_object_or_404(Course, slug=slug, status='published')
    
    favorite, created = CourseFavorite.objects.get_or_create(
        user=request.user,
        course=course
    )
    
    if not created:
        favorite.delete()
        is_favorite = False
        message = f"'{course.title}' retiré de vos favoris."
    else:
        is_favorite = True
        message = f"'{course.title}' ajouté à vos favoris !"
    
    messages.success(request, message)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'is_favorite': is_favorite,
            'message': message
        })
    
    return redirect('courses:course_detail', slug=course.slug)


@login_required
def my_courses(request):
    """Liste des cours de l'utilisateur"""
    enrollments = Enrollment.objects.filter(
        user=request.user,
        status='active'
    ).select_related('course', 'current_lesson').order_by('-enrolled_at')
    
    context = {
        'enrollments': enrollments,
        'total_courses': enrollments.count(),
    }
    
    return render(request, 'courses/my_courses.html', context)


@login_required
def my_favorites(request):
    """Liste des cours favoris de l'utilisateur"""
    favorites = CourseFavorite.objects.filter(
        user=request.user
    ).select_related('course').order_by('-added_at')
    
    context = {
        'favorites': favorites,
        'total_favorites': favorites.count(),
    }
    
    return render(request, 'courses/my_favorites.html', context)
