from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required


def role_required(*roles):
    """
    Decorator for views that checks whether a user has a particular role,
    redirecting to the login page if necessary.
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped_view(request, *args, **kwargs):
            if request.user.role in roles:
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, "Vous n'avez pas l'autorisation d'accéder à cette page.")
                return HttpResponseForbidden("Accès refusé : rôle insuffisant.")
        return wrapped_view
    return decorator


def student_required(view_func):
    """Decorator for views that require student role."""
    return role_required('student')(view_func)


def instructor_required(view_func):
    """Decorator for views that require instructor role."""
    return role_required('instructor')(view_func)


def admin_required(view_func):
    """Decorator for views that require admin role."""
    return role_required('admin')(view_func)


def instructor_or_admin_required(view_func):
    """Decorator for views that require instructor or admin role."""
    return role_required('instructor', 'admin')(view_func)


# Class-based view mixins
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class RoleRequiredMixin(LoginRequiredMixin):
    """Mixin for class-based views that require specific roles."""
    required_roles = []
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        if request.user.role not in self.required_roles:
            messages.error(request, "Vous n'avez pas l'autorisation d'accéder à cette page.")
            raise PermissionDenied("Accès refusé : rôle insuffisant.")
        
        return super().dispatch(request, *args, **kwargs)


class StudentRequiredMixin(RoleRequiredMixin):
    required_roles = ['student']


class InstructorRequiredMixin(RoleRequiredMixin):
    required_roles = ['instructor']


class AdminRequiredMixin(RoleRequiredMixin):
    required_roles = ['admin']


class InstructorOrAdminRequiredMixin(RoleRequiredMixin):
    required_roles = ['instructor', 'admin']