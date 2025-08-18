from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.contrib.auth.views import LoginView as DjangoLoginView, LogoutView as DjangoLogoutView
from django.contrib.auth import login
from django.contrib import messages
from django.urls import reverse_lazy
from django.views import View
from users.models import User
from .forms import CustomUserCreationForm

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
            messages.success(request, 'Votre compte a été créé avec succès !')
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Veuillez corriger les erreurs ci-dessous.')
        return render(request, self.template_name, {'form': form})

class LogoutView(DjangoLogoutView):
    next_page = reverse_lazy('home')
    
    def dispatch(self, request, *args, **kwargs):
        messages.success(request, 'Vous avez été déconnecté avec succès.')
        return super().dispatch(request, *args, **kwargs)
