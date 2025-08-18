from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView
from django.contrib.auth.views import (
    LoginView as DjangoLoginView, 
    LogoutView as DjangoLogoutView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView
)
from django.contrib.auth import login
from django.contrib import messages
from django.urls import reverse_lazy
from django.views import View
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from users.models import User
from .forms import CustomUserCreationForm, CustomPasswordResetForm, CustomSetPasswordForm
from .permissions import (
    student_required, instructor_required, admin_required,
    StudentRequiredMixin, InstructorRequiredMixin, AdminRequiredMixin
)

class HomeView(TemplateView):
    template_name = 'home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context['user_dashboard'] = True
        return context

class LoginView(DjangoLoginView):
    template_name = 'auth/login.html'
    redirect_authenticated_user = True
    success_url = reverse_lazy('home')
    
    def form_valid(self, form):
        messages.success(self.request, f'Bienvenue {form.get_user().username} !')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Nom d\'utilisateur ou mot de passe incorrect.')
        return super().form_invalid(form)

class SignupView(View):
    template_name = 'auth/signup.html'
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('home')
        form = CustomUserCreationForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Send email verification (in development, it goes to console)
            self.send_verification_email(request, user)
            
            messages.success(request, 'Votre compte a été créé avec succès ! Vérifiez votre email pour activer votre compte.')
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Veuillez corriger les erreurs ci-dessous.')
        return render(request, self.template_name, {'form': form})
    
    def send_verification_email(self, request, user):
        current_site = get_current_site(request)
        subject = 'Activation de votre compte eSchool'
        message = f"""
Bonjour {user.first_name or user.username},

Merci de vous être inscrit sur eSchool !

Pour activer votre compte, cliquez sur le lien ci-dessous :
http://{current_site.domain}/verify-email/{user.email_verification_token}/

Si vous n'avez pas créé ce compte, ignorez cet email.

Merci,
L'équipe eSchool
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@eschool.com',
            [user.email],
            fail_silently=True,
        )

class LogoutView(DjangoLogoutView):
    next_page = reverse_lazy('home')
    
    def dispatch(self, request, *args, **kwargs):
        messages.success(request, 'Vous avez été déconnecté avec succès.')
        return super().dispatch(request, *args, **kwargs)


class CustomPasswordResetView(PasswordResetView):
    template_name = 'auth/password_reset.html'
    form_class = CustomPasswordResetForm
    success_url = reverse_lazy('password_reset_done')
    email_template_name = 'auth/password_reset_email.html'
    
    def form_valid(self, form):
        messages.success(self.request, 'Un email de récupération a été envoyé à votre adresse.')
        return super().form_valid(form)


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'auth/password_reset_done.html'


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'auth/password_reset_confirm.html'
    form_class = CustomSetPasswordForm
    success_url = reverse_lazy('password_reset_complete')
    
    def form_valid(self, form):
        messages.success(self.request, 'Votre mot de passe a été modifié avec succès.')
        return super().form_valid(form)


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'auth/password_reset_complete.html'


class EmailVerificationView(View):
    def get(self, request, token):
        try:
            user = get_object_or_404(User, email_verification_token=token)
            if not user.email_verified:
                user.email_verified = True
                user.save()
                messages.success(request, 'Votre email a été vérifié avec succès !')
            else:
                messages.info(request, 'Votre email est déjà vérifié.')
            return redirect('home')
        except:
            messages.error(request, 'Le lien de vérification est invalide ou a expiré.')
            return redirect('home')


# Demo views for role-based permissions

@student_required
def student_dashboard(request):
    """Dashboard view for students only"""
    return render(request, 'demo/student_dashboard.html', {
        'user': request.user,
        'courses_enrolled': 5,  # Demo data
        'courses_completed': 2,
    })


@instructor_required 
def instructor_dashboard(request):
    """Dashboard view for instructors only"""
    return render(request, 'demo/instructor_dashboard.html', {
        'user': request.user,
        'courses_created': 10,  # Demo data
        'total_students': 150,
    })


@admin_required
def admin_dashboard(request):
    """Dashboard view for admins only"""
    return render(request, 'demo/admin_dashboard.html', {
        'user': request.user,
        'total_users': User.objects.count(),
        'total_students': User.objects.filter(role='student').count(),
        'total_instructors': User.objects.filter(role='instructor').count(),
    })


class StudentDashboardView(StudentRequiredMixin, TemplateView):
    """Class-based view for student dashboard"""
    template_name = 'demo/student_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'user': self.request.user,
            'courses_enrolled': 5,
            'courses_completed': 2,
        })
        return context


@login_required
def user_profile_api(request):
    """API endpoint to get user profile data"""
    user = request.user
    data = {
        'username': user.username,
        'email': user.email,
        'role': user.get_role_display(),
        'email_verified': user.email_verified,
        'is_student': user.is_student,
        'is_instructor': user.is_instructor,
        'is_admin': user.is_admin,
    }
    return JsonResponse(data)
