from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/<int:user_id>/', views.user_profile_detail, name='profile_detail'),
    path('profile/picture/upload/', views.upload_profile_picture, name='upload_profile_picture'),
    path('profile/picture/delete/', views.delete_profile_picture, name='delete_profile_picture'),
    path('api/check-username/', views.check_username_availability, name='check_username'),
    path('api/check-email/', views.check_email_availability, name='check_email'),
]