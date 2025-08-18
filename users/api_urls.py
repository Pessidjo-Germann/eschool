from django.urls import path
from . import api_views

app_name = 'users_api'

urlpatterns = [
    # Profile endpoints
    path('profile/', api_views.CurrentUserProfileView.as_view(), name='current-user-profile'),
    path('profile/<int:pk>/', api_views.UserProfileDetailView.as_view(), name='user-profile-detail'),
    path('profile/picture/upload/', api_views.ProfilePictureUploadView.as_view(), name='upload-profile-picture'),
    path('profile/picture/delete/', api_views.delete_profile_picture, name='delete-profile-picture'),
    path('profile/stats/', api_views.profile_stats, name='profile-stats'),
    
    # Role-specific profile endpoints
    path('profile/student/', api_views.StudentProfileView.as_view(), name='student-profile'),
    path('profile/student/<int:user_id>/', api_views.StudentProfileView.as_view(), name='student-profile-detail'),
    path('profile/instructor/', api_views.InstructorProfileView.as_view(), name='instructor-profile'),
    path('profile/instructor/<int:user_id>/', api_views.InstructorProfileView.as_view(), name='instructor-profile-detail'),
    path('profile/admin/', api_views.AdminProfileView.as_view(), name='admin-profile'),
    path('profile/admin/<int:user_id>/', api_views.AdminProfileView.as_view(), name='admin-profile-detail'),
    
    # Users list
    path('users/', api_views.UsersListView.as_view(), name='users-list'),
    
    # Utility endpoints
    path('change-password/', api_views.change_password, name='change-password'),
    path('check-username/', api_views.check_username_availability, name='check-username'),
    path('check-email/', api_views.check_email_availability, name='check-email'),
]