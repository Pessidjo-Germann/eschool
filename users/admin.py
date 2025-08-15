from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'first_name', 'last_name', 'is_staff', 'date_joined')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('-date_joined',)
    
    fieldsets = UserAdmin.fieldsets + (
        ('Role & Profile', {
            'fields': ('role', 'phone_number', 'date_of_birth', 'profile_picture', 'bio')
        }),
        ('Student Info', {
            'fields': ('enrollment_date',),
            'classes': ('collapse',)
        }),
        ('Instructor Info', {
            'fields': ('qualifications', 'experience_years', 'specialization'),
            'classes': ('collapse',)
        }),
    )
