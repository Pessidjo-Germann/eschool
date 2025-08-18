from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
from PIL import Image
import uuid


class User(AbstractUser):
    USER_ROLES = (
        ('student', 'Student'),
        ('instructor', 'Instructor'),
        ('admin', 'Admin'),
    )
    
    role = models.CharField(max_length=20, choices=USER_ROLES, default='student')
    phone_number = models.CharField(
        max_length=15, 
        blank=True, 
        null=True,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message="Le numéro de téléphone doit être au format valide."
        )]
    )
    date_of_birth = models.DateField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True)
    
    # Email verification fields
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(default=uuid.uuid4, editable=False)
    
    # Student specific fields
    enrollment_date = models.DateTimeField(blank=True, null=True)
    
    # Instructor specific fields
    qualifications = models.TextField(blank=True)
    experience_years = models.IntegerField(default=0)
    specialization = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    @property
    def is_student(self):
        return self.role == 'student'
    
    @property
    def is_instructor(self):
        return self.role == 'instructor'
    
    @property
    def is_admin(self):
        return self.role == 'admin'
    
    def save(self, *args, **kwargs):
        # Set enrollment_date for students when created
        if self.role == 'student' and not self.enrollment_date and not self.pk:
            self.enrollment_date = timezone.now()
            
        super().save(*args, **kwargs)
        
        # Resize profile picture if uploaded
        if self.profile_picture:
            self.resize_profile_picture()
    
    def resize_profile_picture(self):
        try:
            img = Image.open(self.profile_picture.path)
            if img.height > 300 or img.width > 300:
                output_size = (300, 300)
                img.thumbnail(output_size)
                img.save(self.profile_picture.path)
        except Exception:
            pass


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField(max_length=20, unique=True)
    current_grade = models.CharField(max_length=50, blank=True)
    parent_contact = models.CharField(max_length=15, blank=True)
    emergency_contact = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    academic_year = models.CharField(max_length=20, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Profil étudiant - {self.user.username}"
    
    def save(self, *args, **kwargs):
        if not self.student_id:
            self.student_id = f"STU{self.user.id:06d}"
        super().save(*args, **kwargs)


class InstructorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='instructor_profile')
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100, blank=True)
    subjects_taught = models.ManyToManyField('courses.Course', blank=True, related_name='instructors')
    office_location = models.CharField(max_length=100, blank=True)
    office_hours = models.TextField(blank=True)
    research_interests = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Profil enseignant - {self.user.username}"
    
    def save(self, *args, **kwargs):
        if not self.employee_id:
            self.employee_id = f"INS{self.user.id:06d}"
        super().save(*args, **kwargs)


class AdminProfile(models.Model):
    PERMISSION_LEVELS = (
        ('basic', 'Basique'),
        ('advanced', 'Avancé'),
        ('super', 'Super Admin'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    admin_id = models.CharField(max_length=20, unique=True)
    permission_level = models.CharField(max_length=20, choices=PERMISSION_LEVELS, default='basic')
    department = models.CharField(max_length=100, blank=True)
    responsibilities = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Profil admin - {self.user.username}"
    
    def save(self, *args, **kwargs):
        if not self.admin_id:
            self.admin_id = f"ADM{self.user.id:06d}"
        super().save(*args, **kwargs)
