from django.urls import path
from .views import (
    HomeView, LoginView, SignupView, LogoutView,
    CustomPasswordResetView, CustomPasswordResetDoneView,
    CustomPasswordResetConfirmView, CustomPasswordResetCompleteView,
    EmailVerificationView, student_dashboard, instructor_dashboard,
    admin_dashboard, StudentDashboardView, user_profile_api
)

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('login/', LoginView.as_view(), name='login'),
    path('signup/', SignupView.as_view(), name='signup'),
    path('logout/', LogoutView.as_view(), name='logout'),
    
    # Email verification
    path('verify-email/<uuid:token>/', EmailVerificationView.as_view(), name='verify_email'),
    
    # Password reset URLs
    path('password-reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    
    # Role-based demo dashboards
    path('student-dashboard/', student_dashboard, name='student_dashboard'),
    path('instructor-dashboard/', instructor_dashboard, name='instructor_dashboard'),
    path('admin-dashboard/', admin_dashboard, name='admin_dashboard'),
    path('student-dashboard-cbv/', StudentDashboardView.as_view(), name='student_dashboard_cbv'),
    
    # API endpoints
    path('api/user-profile/', user_profile_api, name='user_profile_api'),
]
