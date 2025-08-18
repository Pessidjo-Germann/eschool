from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import User, StudentProfile, InstructorProfile, AdminProfile


class UserBasicSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'full_name', 'role', 'role_display', 'profile_picture',
            'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']


class UserProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'full_name', 'role', 'role_display', 'phone_number',
            'date_of_birth', 'profile_picture', 'bio', 'email_verified',
            'enrollment_date', 'qualifications', 'experience_years', 
            'specialization', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'role', 'email_verified', 'created_at', 'updated_at']
    
    def validate_email(self, value):
        user = self.instance
        if user and User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("Cette adresse email est déjà utilisée.")
        return value
    
    def validate_username(self, value):
        user = self.instance
        if user and User.objects.filter(username=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("Ce nom d'utilisateur est déjà pris.")
        return value
    
    def validate_experience_years(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Les années d'expérience ne peuvent pas être négatives.")
        if value is not None and value > 50:
            raise serializers.ValidationError("Les années d'expérience semblent trop élevées.")
        return value


class StudentProfileSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = StudentProfile
        fields = [
            'id', 'user', 'student_id', 'current_grade', 'parent_contact',
            'emergency_contact', 'address', 'academic_year', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'student_id', 'created_at', 'updated_at']


class InstructorProfileSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = InstructorProfile
        fields = [
            'id', 'user', 'employee_id', 'department',
            'office_location', 'office_hours',
            'research_interests', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'employee_id', 'created_at', 'updated_at']


class AdminProfileSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)
    permission_level_display = serializers.CharField(
        source='get_permission_level_display', read_only=True
    )
    
    class Meta:
        model = AdminProfile
        fields = [
            'id', 'user', 'admin_id', 'permission_level', 
            'permission_level_display', 'department', 'responsibilities',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'admin_id', 'created_at', 'updated_at']


class UserDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    student_profile = StudentProfileSerializer(read_only=True)
    instructor_profile = InstructorProfileSerializer(read_only=True)
    admin_profile = AdminProfileSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'full_name', 'role', 'role_display', 'phone_number',
            'date_of_birth', 'profile_picture', 'bio', 'email_verified',
            'enrollment_date', 'qualifications', 'experience_years', 
            'specialization', 'is_active', 'date_joined', 'last_login',
            'created_at', 'updated_at', 'student_profile', 
            'instructor_profile', 'admin_profile'
        ]
        read_only_fields = [
            'id', 'role', 'email_verified', 'is_active', 
            'date_joined', 'last_login', 'created_at', 'updated_at'
        ]


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    
    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Le mot de passe actuel est incorrect.")
        return value
    
    def validate_new_password(self, value):
        try:
            validate_password(value, self.context['request'].user)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'Les mots de passe ne correspondent pas.'
            })
        return attrs
    
    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class ProfilePictureSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['profile_picture']
    
    def validate_profile_picture(self, value):
        if value:
            if value.size > 5 * 1024 * 1024:  # 5MB limit
                raise serializers.ValidationError(
                    "La taille de l'image ne peut pas dépasser 5MB."
                )
            
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif']
            if not any(value.name.lower().endswith(ext) for ext in valid_extensions):
                raise serializers.ValidationError(
                    "Format d'image non supporté. Utilisez JPG, PNG ou GIF."
                )
        
        return value