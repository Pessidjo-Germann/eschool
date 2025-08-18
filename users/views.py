from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.core.exceptions import PermissionDenied
from .models import User, StudentProfile, InstructorProfile, AdminProfile
from .forms import (
    UserProfileForm, StudentProfileForm, InstructorProfileForm, 
    AdminProfileForm, InstructorQualificationsForm, ProfilePictureForm
)


@login_required
def profile_view(request):
    user = request.user
    context = {'user': user}
    
    try:
        if user.is_student:
            profile = user.student_profile
            context['profile'] = profile
            context['profile_type'] = 'student'
        elif user.is_instructor:
            profile = user.instructor_profile
            context['profile'] = profile
            context['profile_type'] = 'instructor'
        elif user.is_admin:
            profile = user.admin_profile
            context['profile'] = profile
            context['profile_type'] = 'admin'
    except (StudentProfile.DoesNotExist, InstructorProfile.DoesNotExist, AdminProfile.DoesNotExist):
        context['profile'] = None
        context['profile_type'] = 'basic'
    
    return render(request, 'users/profile.html', context)


@login_required
def edit_profile(request):
    user = request.user
    
    # Get or create the specific profile based on user role
    profile = None
    if user.is_student:
        profile, created = StudentProfile.objects.get_or_create(user=user)
        profile_form_class = StudentProfileForm
        profile_type = 'student'
    elif user.is_instructor:
        profile, created = InstructorProfile.objects.get_or_create(user=user)
        profile_form_class = InstructorProfileForm
        profile_type = 'instructor'
    elif user.is_admin:
        profile, created = AdminProfile.objects.get_or_create(user=user)
        profile_form_class = AdminProfileForm
        profile_type = 'admin'
    else:
        profile_form_class = None
        profile_type = 'basic'
    
    if request.method == 'POST':
        user_form = UserProfileForm(request.POST, request.FILES, instance=user)
        
        profile_form = None
        qualifications_form = None
        
        if profile_form_class:
            profile_form = profile_form_class(request.POST, instance=profile)
        
        if user.is_instructor:
            qualifications_form = InstructorQualificationsForm(request.POST, instance=user)
        
        forms_valid = user_form.is_valid()
        if profile_form:
            forms_valid = forms_valid and profile_form.is_valid()
        if qualifications_form:
            forms_valid = forms_valid and qualifications_form.is_valid()
        
        if forms_valid:
            with transaction.atomic():
                user_form.save()
                if profile_form:
                    profile_form.save()
                if qualifications_form:
                    qualifications_form.save()
            
            messages.success(request, 'Votre profil a été mis à jour avec succès!')
            return redirect('users:profile')
    else:
        user_form = UserProfileForm(instance=user)
        profile_form = profile_form_class(instance=profile) if profile_form_class else None
        qualifications_form = InstructorQualificationsForm(instance=user) if user.is_instructor else None
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'qualifications_form': qualifications_form,
        'profile_type': profile_type,
        'user': user,
    }
    
    return render(request, 'users/edit_profile.html', context)


@login_required
@require_http_methods(["POST"])
def upload_profile_picture(request):
    form = ProfilePictureForm(request.POST, request.FILES, instance=request.user)
    
    if form.is_valid():
        form.save()
        return JsonResponse({
            'success': True,
            'message': 'Photo de profil mise à jour avec succès!',
            'image_url': request.user.profile_picture.url if request.user.profile_picture else None
        })
    else:
        errors = []
        for field_errors in form.errors.values():
            errors.extend(field_errors)
        
        return JsonResponse({
            'success': False,
            'message': 'Erreur lors de la mise à jour de la photo de profil.',
            'errors': errors
        })


@login_required
def user_profile_detail(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    
    # Check permissions - users can only view certain profiles
    if request.user != target_user and not request.user.is_admin:
        if request.user.is_student and not target_user.is_instructor:
            raise PermissionDenied("Vous ne pouvez pas voir ce profil.")
    
    context = {'target_user': target_user}
    
    try:
        if target_user.is_student:
            profile = target_user.student_profile
            context['profile'] = profile
            context['profile_type'] = 'student'
        elif target_user.is_instructor:
            profile = target_user.instructor_profile
            context['profile'] = profile
            context['profile_type'] = 'instructor'
        elif target_user.is_admin:
            profile = target_user.admin_profile
            context['profile'] = profile
            context['profile_type'] = 'admin'
    except (StudentProfile.DoesNotExist, InstructorProfile.DoesNotExist, AdminProfile.DoesNotExist):
        context['profile'] = None
        context['profile_type'] = 'basic'
    
    return render(request, 'users/profile_detail.html', context)


@login_required
def delete_profile_picture(request):
    if request.method == 'POST':
        user = request.user
        if user.profile_picture:
            user.profile_picture.delete(save=True)
            messages.success(request, 'Photo de profil supprimée avec succès!')
        else:
            messages.info(request, 'Aucune photo de profil à supprimer.')
        
        return redirect('users:profile')
    
    return redirect('users:profile')


def check_username_availability(request):
    username = request.GET.get('username', '')
    if len(username) < 3:
        return JsonResponse({'available': False, 'message': 'Le nom d\'utilisateur doit contenir au moins 3 caractères.'})
    
    exists = User.objects.filter(username=username).exclude(id=request.user.id if request.user.is_authenticated else None).exists()
    
    return JsonResponse({
        'available': not exists,
        'message': 'Ce nom d\'utilisateur est déjà pris.' if exists else 'Ce nom d\'utilisateur est disponible.'
    })


def check_email_availability(request):
    email = request.GET.get('email', '')
    if not email:
        return JsonResponse({'available': False, 'message': 'Veuillez entrer une adresse email.'})
    
    exists = User.objects.filter(email=email).exclude(id=request.user.id if request.user.is_authenticated else None).exists()
    
    return JsonResponse({
        'available': not exists,
        'message': 'Cette adresse email est déjà utilisée.' if exists else 'Cette adresse email est disponible.'
    })
