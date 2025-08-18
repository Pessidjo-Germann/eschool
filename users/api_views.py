from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.db import models
from .models import User, StudentProfile, InstructorProfile, AdminProfile
from .serializers import (
    UserProfileSerializer, UserDetailSerializer, StudentProfileSerializer,
    InstructorProfileSerializer, AdminProfileSerializer, PasswordChangeSerializer,
    ProfilePictureSerializer, UserBasicSerializer
)


class IsOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if isinstance(obj, User):
            return obj == request.user or request.user.is_staff or request.user.is_admin
        else:
            return obj.user == request.user or request.user.is_staff or request.user.is_admin


class CanViewProfile(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user
        target_user = obj if isinstance(obj, User) else obj.user
        
        if user == target_user or user.is_admin:
            return True
        
        if user.is_student and target_user.is_instructor:
            return True
            
        if user.is_instructor and target_user.is_student:
            return True
            
        return False


class UserProfileDetailView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAuthenticated, CanViewProfile]
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return UserDetailSerializer
        return UserProfileSerializer
    
    def get_object(self):
        user_id = self.kwargs.get('pk')
        if user_id:
            return get_object_or_404(User, id=user_id)
        return self.request.user


class CurrentUserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return UserDetailSerializer
        return UserProfileSerializer


class StudentProfileView(generics.RetrieveUpdateAPIView):
    queryset = StudentProfile.objects.all()
    serializer_class = StudentProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    
    def get_object(self):
        user_id = self.kwargs.get('user_id')
        if user_id:
            user = get_object_or_404(User, id=user_id)
            profile, created = StudentProfile.objects.get_or_create(user=user)
            return profile
        
        if not self.request.user.is_student:
            raise PermissionDenied("Vous n'êtes pas un étudiant.")
        
        profile, created = StudentProfile.objects.get_or_create(user=self.request.user)
        return profile


class InstructorProfileView(generics.RetrieveUpdateAPIView):
    queryset = InstructorProfile.objects.all()
    serializer_class = InstructorProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    
    def get_object(self):
        user_id = self.kwargs.get('user_id')
        if user_id:
            user = get_object_or_404(User, id=user_id)
            profile, created = InstructorProfile.objects.get_or_create(user=user)
            return profile
        
        if not self.request.user.is_instructor:
            raise PermissionDenied("Vous n'êtes pas un enseignant.")
        
        profile, created = InstructorProfile.objects.get_or_create(user=self.request.user)
        return profile


class AdminProfileView(generics.RetrieveUpdateAPIView):
    queryset = AdminProfile.objects.all()
    serializer_class = AdminProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    
    def get_object(self):
        user_id = self.kwargs.get('user_id')
        if user_id:
            user = get_object_or_404(User, id=user_id)
            profile, created = AdminProfile.objects.get_or_create(user=user)
            return profile
        
        if not self.request.user.is_admin:
            raise PermissionDenied("Vous n'êtes pas un administrateur.")
        
        profile, created = AdminProfile.objects.get_or_create(user=self.request.user)
        return profile


class ProfilePictureUploadView(generics.UpdateAPIView):
    serializer_class = ProfilePictureSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_object(self):
        return self.request.user
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            'message': 'Photo de profil mise à jour avec succès!',
            'profile_picture': instance.profile_picture.url if instance.profile_picture else None
        })


class UsersListView(generics.ListAPIView):
    queryset = User.objects.all().select_related(
        'student_profile', 'instructor_profile', 'admin_profile'
    )
    serializer_class = UserBasicSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(username__icontains=search) |
                models.Q(first_name__icontains=search) |
                models.Q(last_name__icontains=search) |
                models.Q(email__icontains=search)
            )
        
        if not self.request.user.is_admin:
            if self.request.user.is_student:
                queryset = queryset.filter(
                    models.Q(role='instructor') | models.Q(id=self.request.user.id)
                )
            elif self.request.user.is_instructor:
                queryset = queryset.filter(
                    models.Q(role='student') | models.Q(id=self.request.user.id)
                )
        
        return queryset.filter(is_active=True)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def change_password(request):
    serializer = PasswordChangeSerializer(
        data=request.data,
        context={'request': request}
    )
    
    if serializer.is_valid():
        serializer.save()
        return Response({
            'message': 'Mot de passe modifié avec succès!'
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_profile_picture(request):
    user = request.user
    
    if user.profile_picture:
        user.profile_picture.delete(save=True)
        return Response({
            'message': 'Photo de profil supprimée avec succès!'
        }, status=status.HTTP_200_OK)
    
    return Response({
        'message': 'Aucune photo de profil à supprimer.'
    }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
def check_username_availability(request):
    username = request.GET.get('username', '')
    user_id = request.GET.get('user_id', None)
    
    if len(username) < 3:
        return Response({
            'available': False,
            'message': 'Le nom d\'utilisateur doit contenir au moins 3 caractères.'
        })
    
    queryset = User.objects.filter(username=username)
    if user_id:
        queryset = queryset.exclude(id=user_id)
    
    exists = queryset.exists()
    
    return Response({
        'available': not exists,
        'message': 'Ce nom d\'utilisateur est déjà pris.' if exists 
                  else 'Ce nom d\'utilisateur est disponible.'
    })


@api_view(['GET'])
def check_email_availability(request):
    email = request.GET.get('email', '')
    user_id = request.GET.get('user_id', None)
    
    if not email:
        return Response({
            'available': False,
            'message': 'Veuillez entrer une adresse email.'
        })
    
    queryset = User.objects.filter(email=email)
    if user_id:
        queryset = queryset.exclude(id=user_id)
    
    exists = queryset.exists()
    
    return Response({
        'available': not exists,
        'message': 'Cette adresse email est déjà utilisée.' if exists 
                  else 'Cette adresse email est disponible.'
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def profile_stats(request):
    user = request.user
    stats = {
        'profile_completion': 0,
        'missing_fields': [],
        'last_updated': user.updated_at,
        'account_age_days': (timezone.now() - user.date_joined).days
    }
    
    required_fields = ['first_name', 'last_name', 'email', 'phone_number', 'bio']
    filled_fields = 0
    
    for field in required_fields:
        value = getattr(user, field, None)
        if value and str(value).strip():
            filled_fields += 1
        else:
            stats['missing_fields'].append(field)
    
    if user.profile_picture:
        filled_fields += 1
    else:
        stats['missing_fields'].append('profile_picture')
    
    if user.date_of_birth:
        filled_fields += 1
    else:
        stats['missing_fields'].append('date_of_birth')
    
    stats['profile_completion'] = int((filled_fields / 7) * 100)
    
    return Response(stats)