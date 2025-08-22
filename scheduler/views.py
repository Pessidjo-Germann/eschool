from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Q
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from datetime import datetime, timedelta, date
from calendar import monthrange
import json
from icalendar import Calendar, Event as ICalEvent, vText
from django.utils.dateformat import format

from .models import Event, CourseSchedule, ScheduleAttendance, EventReminder
from courses.models import Course, Enrollment

@login_required
def calendar_view(request):
    """Vue principale du calendrier"""
    today = timezone.now().date()
    
    # Paramètres de la vue
    view_type = request.GET.get('view', 'month')  # month, week, day
    current_date = request.GET.get('date')
    
    if current_date:
        try:
            current_date = datetime.strptime(current_date, '%Y-%m-%d').date()
        except ValueError:
            current_date = today
    else:
        current_date = today
    
    context = {
        'today': today,
        'current_date': current_date,
        'view_type': view_type,
    }
    
    return render(request, 'scheduler/calendar.html', context)

@login_required
def calendar_api(request):
    """API pour récupérer les événements du calendrier"""
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    view_type = request.GET.get('view', 'month')
    
    if not start_date or not end_date:
        return JsonResponse({'error': 'Dates de début et fin requises'}, status=400)
    
    try:
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    except ValueError:
        return JsonResponse({'error': 'Format de date invalide'}, status=400)
    
    # Récupérer les événements de l'utilisateur
    events = Event.objects.filter(
        Q(organizer=request.user) | Q(participants=request.user),
        start_date__lte=end_dt,
        end_date__gte=start_dt,
        is_active=True
    ).distinct()
    
    # Récupérer les cours planifiés pour l'utilisateur
    enrolled_courses = Enrollment.objects.filter(
        user=request.user,
        status='active'
    ).values_list('course_id', flat=True)
    
    course_schedules = CourseSchedule.objects.filter(
        Q(course__instructor=request.user) | Q(course_id__in=enrolled_courses),
        scheduled_date__lte=end_dt,
        scheduled_date__date__lte=end_dt.date()
    ).select_related('course')
    
    # Convertir en format FullCalendar
    calendar_events = []
    
    # Événements génériques
    for event in events:
        calendar_events.append({
            'id': f'event_{event.id}',
            'title': event.title,
            'start': event.start_date.isoformat(),
            'end': event.end_date.isoformat(),
            'allDay': event.all_day,
            'backgroundColor': event.color,
            'borderColor': event.color,
            'textColor': '#ffffff' if _is_dark_color(event.color) else '#000000',
            'extendedProps': {
                'type': 'event',
                'eventType': event.event_type,
                'priority': event.priority,
                'description': event.description,
                'location': event.location,
                'onlineLink': event.online_link,
                'organizerId': event.organizer.id,
                'participantsCount': event.get_participants_count(),
                'isParticipant': event.is_participant(request.user),
                'canEdit': event.organizer == request.user
            }
        })
    
    # Cours planifiés
    for schedule in course_schedules:
        is_enrolled = schedule.course.id in enrolled_courses
        is_instructor = schedule.course.instructor == request.user
        
        # Couleur selon le type
        color_map = {
            'live': '#28a745',      # Vert pour cours en direct
            'deadline': '#dc3545',   # Rouge pour échéances
            'exam': '#fd7e14',      # Orange pour examens
            'assignment': '#6f42c1'  # Violet pour devoirs
        }
        
        calendar_events.append({
            'id': f'schedule_{schedule.id}',
            'title': f"{schedule.course.title} - {schedule.get_schedule_type_display()}",
            'start': schedule.scheduled_date.isoformat(),
            'end': schedule.end_date.isoformat(),
            'backgroundColor': color_map.get(schedule.schedule_type, '#007bff'),
            'borderColor': color_map.get(schedule.schedule_type, '#007bff'),
            'textColor': '#ffffff',
            'extendedProps': {
                'type': 'course_schedule',
                'scheduleType': schedule.schedule_type,
                'status': schedule.status,
                'courseTitle': schedule.course.title,
                'instructorName': schedule.course.instructor.get_full_name() or schedule.course.instructor.username,
                'isEnrolled': is_enrolled,
                'isInstructor': is_instructor,
                'accessLink': schedule.access_link if is_enrolled or is_instructor else None,
                'maxParticipants': schedule.max_participants,
                'enrolledCount': schedule.get_enrolled_count(),
                'attendanceCount': schedule.attendance_count,
                'canEdit': is_instructor
            }
        })
    
    return JsonResponse({'events': calendar_events})

def _is_dark_color(hex_color):
    """Détermine si une couleur est foncée pour ajuster le texte"""
    try:
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        brightness = sum(rgb) / 3
        return brightness < 128
    except:
        return False

@login_required
def create_event(request):
    """Créer un nouvel événement"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Validation des données
            required_fields = ['title', 'start_date', 'end_date']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({'error': f'Le champ {field} est requis'}, status=400)
            
            # Conversion des dates
            start_date = datetime.fromisoformat(data['start_date'].replace('Z', '+00:00'))
            end_date = datetime.fromisoformat(data['end_date'].replace('Z', '+00:00'))
            
            if end_date <= start_date:
                return JsonResponse({'error': 'La date de fin doit être postérieure à la date de début'}, status=400)
            
            # Créer l'événement
            event = Event.objects.create(
                title=data['title'],
                description=data.get('description', ''),
                event_type=data.get('event_type', 'reminder'),
                priority=data.get('priority', 'medium'),
                start_date=start_date,
                end_date=end_date,
                all_day=data.get('all_day', False),
                organizer=request.user,
                location=data.get('location', ''),
                online_link=data.get('online_link', ''),
                color=data.get('color', '#3498db'),
                is_public=data.get('is_public', False),
                reminder_enabled=data.get('reminder_enabled', True),
                reminder_minutes_before=data.get('reminder_minutes_before', 15),
                email_reminder=data.get('email_reminder', False)
            )
            
            # Ajouter des participants si spécifiés
            participant_ids = data.get('participants', [])
            if participant_ids:
                event.participants.set(participant_ids)
            
            return JsonResponse({
                'success': True,
                'event_id': str(event.id),
                'message': 'Événement créé avec succès'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalide'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

@login_required
def update_event(request, event_id):
    """Mettre à jour un événement"""
    event = get_object_or_404(Event, id=event_id)
    
    # Vérifier les permissions
    if event.organizer != request.user:
        return JsonResponse({'error': 'Permission refusée'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Mettre à jour les champs
            if 'title' in data:
                event.title = data['title']
            if 'description' in data:
                event.description = data['description']
            if 'start_date' in data:
                event.start_date = datetime.fromisoformat(data['start_date'].replace('Z', '+00:00'))
            if 'end_date' in data:
                event.end_date = datetime.fromisoformat(data['end_date'].replace('Z', '+00:00'))
            if 'all_day' in data:
                event.all_day = data['all_day']
            if 'color' in data:
                event.color = data['color']
            if 'location' in data:
                event.location = data['location']
            if 'online_link' in data:
                event.online_link = data['online_link']
            
            event.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Événement mis à jour'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalide'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

@login_required
def delete_event(request, event_id):
    """Supprimer un événement"""
    event = get_object_or_404(Event, id=event_id)
    
    # Vérifier les permissions
    if event.organizer != request.user:
        return JsonResponse({'error': 'Permission refusée'}, status=403)
    
    if request.method == 'DELETE':
        event.delete()
        return JsonResponse({'success': True, 'message': 'Événement supprimé'})
    
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

@login_required
def export_ical(request):
    """Export des événements au format iCal"""
    # Paramètres de date
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    
    if start_date:
        start_dt = datetime.fromisoformat(start_date)
    else:
        start_dt = timezone.now() - timedelta(days=30)
    
    if end_date:
        end_dt = datetime.fromisoformat(end_date)
    else:
        end_dt = timezone.now() + timedelta(days=365)
    
    # Créer le calendrier iCal
    cal = Calendar()
    cal.add('prodid', '-//eSchool Platform//Calendar//FR')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('method', 'PUBLISH')
    cal.add('x-wr-calname', f'Calendrier eSchool - {request.user.get_full_name() or request.user.username}')
    cal.add('x-wr-caldesc', 'Calendrier personnel eSchool avec cours et événements')
    
    # Récupérer les événements
    events = Event.objects.filter(
        Q(organizer=request.user) | Q(participants=request.user),
        start_date__gte=start_dt,
        start_date__lte=end_dt,
        is_active=True
    ).distinct()
    
    # Ajouter les événements au calendrier
    for event in events:
        cal_event = ICalEvent()
        cal_event.add('uid', f'event_{event.id}@eschool.platform')
        cal_event.add('dtstart', event.start_date)
        cal_event.add('dtend', event.end_date)
        cal_event.add('dtstamp', event.created_at)
        cal_event.add('summary', event.title)
        cal_event.add('description', event.description or '')
        
        if event.location:
            cal_event.add('location', vText(event.location))
        
        if event.online_link:
            cal_event.add('url', event.online_link)
        
        # Catégories
        categories = [event.get_event_type_display()]
        if event.priority != 'medium':
            categories.append(f'Priorité: {event.get_priority_display()}')
        cal_event.add('categories', categories)
        
        # Rappels
        if event.reminder_enabled:
            from icalendar import Alarm
            alarm = Alarm()
            alarm.add('action', 'DISPLAY')
            alarm.add('description', f'Rappel: {event.title}')
            alarm.add('trigger', timedelta(minutes=-event.reminder_minutes_before))
            cal_event.add_component(alarm)
        
        cal.add_component(cal_event)
    
    # Récupérer les cours planifiés
    enrolled_courses = Enrollment.objects.filter(
        user=request.user,
        status='active'
    ).values_list('course_id', flat=True)
    
    course_schedules = CourseSchedule.objects.filter(
        Q(course__instructor=request.user) | Q(course_id__in=enrolled_courses),
        scheduled_date__gte=start_dt,
        scheduled_date__lte=end_dt
    ).select_related('course')
    
    # Ajouter les cours planifiés
    for schedule in course_schedules:
        cal_event = ICalEvent()
        cal_event.add('uid', f'schedule_{schedule.id}@eschool.platform')
        cal_event.add('dtstart', schedule.scheduled_date)
        cal_event.add('dtend', schedule.end_date)
        cal_event.add('dtstamp', schedule.created_at)
        cal_event.add('summary', f"{schedule.course.title} - {schedule.get_schedule_type_display()}")
        
        description_parts = [f"Cours: {schedule.course.title}"]
        if schedule.course.instructor:
            description_parts.append(f"Instructeur: {schedule.course.instructor.get_full_name()}")
        if schedule.notes:
            description_parts.append(f"Notes: {schedule.notes}")
        
        cal_event.add('description', '\n'.join(description_parts))
        
        if schedule.access_link:
            cal_event.add('url', schedule.access_link)
        
        # Catégories
        cal_event.add('categories', ['Cours', schedule.get_schedule_type_display()])
        
        cal.add_component(cal_event)
    
    # Retourner le fichier iCal
    response = HttpResponse(cal.to_ical(), content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="calendrier_eschool_{request.user.username}.ics"'
    return response

@login_required
def upcoming_events(request):
    """API pour les événements à venir"""
    limit = int(request.GET.get('limit', 10))
    days_ahead = int(request.GET.get('days', 7))
    
    end_date = timezone.now() + timedelta(days=days_ahead)
    
    # Événements à venir
    events = Event.objects.filter(
        Q(organizer=request.user) | Q(participants=request.user),
        start_date__gte=timezone.now(),
        start_date__lte=end_date,
        is_active=True
    ).distinct().order_by('start_date')[:limit]
    
    # Cours planifiés à venir
    enrolled_courses = Enrollment.objects.filter(
        user=request.user,
        status='active'
    ).values_list('course_id', flat=True)
    
    course_schedules = CourseSchedule.objects.filter(
        Q(course__instructor=request.user) | Q(course_id__in=enrolled_courses),
        scheduled_date__gte=timezone.now(),
        scheduled_date__lte=end_date
    ).select_related('course').order_by('scheduled_date')[:limit]
    
    # Formater les données
    upcoming = []
    
    for event in events:
        upcoming.append({
            'type': 'event',
            'id': str(event.id),
            'title': event.title,
            'start_date': event.start_date.isoformat(),
            'end_date': event.end_date.isoformat(),
            'event_type': event.event_type,
            'priority': event.priority,
            'location': event.location,
            'online_link': event.online_link,
            'time_until_start': _format_time_until(event.time_until_start),
            'is_upcoming': event.is_upcoming,
            'color': event.color
        })
    
    for schedule in course_schedules:
        upcoming.append({
            'type': 'course_schedule',
            'id': str(schedule.id),
            'title': f"{schedule.course.title} - {schedule.get_schedule_type_display()}",
            'start_date': schedule.scheduled_date.isoformat(),
            'end_date': schedule.end_date.isoformat(),
            'schedule_type': schedule.schedule_type,
            'course_title': schedule.course.title,
            'instructor_name': schedule.course.instructor.get_full_name() or schedule.course.instructor.username,
            'access_link': schedule.access_link,
            'time_until_start': _format_time_until(schedule.scheduled_date - timezone.now()),
            'color': {
                'live': '#28a745',
                'deadline': '#dc3545',
                'exam': '#fd7e14',
                'assignment': '#6f42c1'
            }.get(schedule.schedule_type, '#007bff')
        })
    
    # Trier par date de début
    upcoming.sort(key=lambda x: x['start_date'])
    
    return JsonResponse({'events': upcoming[:limit]})

def _format_time_until(time_delta):
    """Formate la durée jusqu'à un événement"""
    if not time_delta or time_delta.total_seconds() <= 0:
        return None
    
    days = time_delta.days
    hours, remainder = divmod(time_delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    if days > 0:
        return f"Dans {days} jour{'s' if days > 1 else ''}"
    elif hours > 0:
        return f"Dans {hours}h{minutes:02d}"
    else:
        return f"Dans {minutes} minute{'s' if minutes > 1 else ''}"

@login_required 
def join_course_schedule(request, schedule_id):
    """Rejoindre un cours planifié"""
    schedule = get_object_or_404(CourseSchedule, id=schedule_id)
    
    # Vérifier si l'utilisateur est inscrit au cours
    if not Enrollment.objects.filter(
        student=request.user, 
        course=schedule.course, 
        is_active=True
    ).exists() and schedule.course.instructor != request.user:
        return JsonResponse({'error': 'Vous n\'êtes pas inscrit à ce cours'}, status=403)
    
    # Créer ou mettre à jour la présence
    attendance, created = ScheduleAttendance.objects.get_or_create(
        schedule=schedule,
        student=request.user,
        defaults={'registered': True}
    )
    
    if not attendance.join_time and schedule.is_current:
        attendance.join_time = timezone.now()
        attendance.attended = True
        attendance.save()
    
    response_data = {
        'success': True,
        'access_link': schedule.access_link,
        'meeting_id': schedule.meeting_id,
        'access_code': schedule.access_code
    }
    
    return JsonResponse(response_data)
