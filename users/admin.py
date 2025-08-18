from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import User, StudentProfile, InstructorProfile, AdminProfile


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'username', 'email', 'get_full_name', 'role', 'email_verified', 
        'is_active', 'is_staff', 'date_joined'
    )
    list_filter = (
        'role', 'email_verified', 'is_staff', 'is_superuser', 
        'is_active', 'date_joined'
    )
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone_number')
    ordering = ('-date_joined',)
    readonly_fields = ('date_joined', 'last_login', 'email_verification_token', 'created_at', 'updated_at')
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {
            'fields': (
                'first_name', 'last_name', 'email', 'phone_number', 
                'date_of_birth', 'profile_picture', 'bio'
            )
        }),
        ('Role & Permissions', {
            'fields': (
                'role', 'email_verified', 'is_active', 'is_staff', 
                'is_superuser', 'groups', 'user_permissions'
            )
        }),
        ('Student Info', {
            'fields': ('enrollment_date',),
            'classes': ('collapse',)
        }),
        ('Instructor Info', {
            'fields': ('qualifications', 'experience_years', 'specialization'),
            'classes': ('collapse',)
        }),
        ('Important dates', {
            'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')
        }),
        ('Email Verification', {
            'fields': ('email_verification_token',),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'role', 'password1', 'password2'),
        }),
    )
    
    def get_full_name(self, obj):
        return obj.get_full_name() or '-'
    get_full_name.short_description = 'Full Name'
    
    def email_verified(self, obj):
        if obj.email_verified:
            return format_html('<span style="color: green;">✓ Verified</span>')
        return format_html('<span style="color: red;">✗ Not verified</span>')
    email_verified.short_description = 'Email Status'


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = (
        'student_id', 'user', 'current_grade', 'academic_year', 
        'parent_contact', 'created_at'
    )
    list_filter = ('current_grade', 'academic_year', 'created_at')
    search_fields = (
        'student_id', 'user__username', 'user__first_name', 
        'user__last_name', 'user__email', 'current_grade'
    )
    readonly_fields = ('student_id', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('User Info', {
            'fields': ('user', 'student_id')
        }),
        ('Academic Info', {
            'fields': ('current_grade', 'academic_year', 'address')
        }),
        ('Contact Info', {
            'fields': ('parent_contact', 'emergency_contact')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(InstructorProfile)
class InstructorProfileAdmin(admin.ModelAdmin):
    list_display = (
        'employee_id', 'user', 'department', 'office_location', 
        'subjects_count', 'created_at'
    )
    list_filter = ('department', 'created_at')
    search_fields = (
        'employee_id', 'user__username', 'user__first_name', 
        'user__last_name', 'user__email', 'department', 'office_location'
    )
    readonly_fields = ('employee_id', 'created_at', 'updated_at')
    filter_horizontal = ('subjects_taught',)
    ordering = ('-created_at',)
    
    fieldsets = (
        ('User Info', {
            'fields': ('user', 'employee_id')
        }),
        ('Professional Info', {
            'fields': ('department', 'subjects_taught', 'office_location', 'office_hours')
        }),
        ('Research & Interests', {
            'fields': ('research_interests',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def subjects_count(self, obj):
        return obj.subjects_taught.count()
    subjects_count.short_description = 'Cours enseignés'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').prefetch_related('subjects_taught')


@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = (
        'admin_id', 'user', 'permission_level', 'department', 'created_at'
    )
    list_filter = ('permission_level', 'department', 'created_at')
    search_fields = (
        'admin_id', 'user__username', 'user__first_name', 
        'user__last_name', 'user__email', 'department'
    )
    readonly_fields = ('admin_id', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('User Info', {
            'fields': ('user', 'admin_id')
        }),
        ('Admin Settings', {
            'fields': ('permission_level', 'department', 'responsibilities')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


# Custom admin site configuration
admin.site.site_header = 'eSchool Administration'
admin.site.site_title = 'eSchool Admin'
admin.site.index_title = 'Bienvenue dans l\'administration eSchool'
