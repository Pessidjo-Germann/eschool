from django.urls import path
from . import views

app_name = 'scheduler'

urlpatterns = [
    # Vue principale du calendrier
    path('', views.calendar_view, name='calendar'),
    
    # API endpoints
    path('api/events/', views.calendar_api, name='calendar_api'),
    path('api/events/create/', views.create_event, name='create_event'),
    path('api/events/<uuid:event_id>/update/', views.update_event, name='update_event'),
    path('api/events/<uuid:event_id>/delete/', views.delete_event, name='delete_event'),
    path('api/upcoming/', views.upcoming_events, name='upcoming_events'),
    
    # Export iCal
    path('export/ical/', views.export_ical, name='export_ical'),
    
    # Cours planifiés
    path('schedule/<uuid:schedule_id>/join/', views.join_course_schedule, name='join_schedule'),
]