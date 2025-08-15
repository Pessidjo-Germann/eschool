from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'admin')

class IsFormateur(BasePermission):
    """
    Allows access only to instructor users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'formateur')

class IsApprenant(BasePermission):
    """
    Allows access only to student users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'apprenant')
