from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
from .models import Event, CourseSchedule, EventReminder
from courses.models import Enrollment

class ReminderService:
    """Service pour gérer les rappels automatiques"""
    
    @classmethod
    def create_event_reminders(cls, event):
        """Crée des rappels pour un événement"""
        if not event.reminder_enabled:
            return
        
        reminder_time = event.start_date - timedelta(minutes=event.reminder_minutes_before)
        
        # Rappel pour l'organisateur
        EventReminder.objects.get_or_create(
            event=event,
            user=event.organizer,
            reminder_type='email' if event.email_reminder else 'in_app',
            defaults={
                'scheduled_send_time': reminder_time,
                'subject': f"Rappel: {event.title}",
                'message': cls._format_event_message(event)
            }
        )
        
        # Rappels pour les participants
        for participant in event.participants.all():
            EventReminder.objects.get_or_create(
                event=event,
                user=participant,
                reminder_type='email' if event.email_reminder else 'in_app',
                defaults={
                    'scheduled_send_time': reminder_time,
                    'subject': f"Rappel: {event.title}",
                    'message': cls._format_event_message(event)
                }
            )
    
    @classmethod
    def create_schedule_reminders(cls, schedule):
        """Crée des rappels pour un cours planifié"""
        if not schedule.auto_reminder:
            return
        
        reminder_time = schedule.scheduled_date - timedelta(hours=schedule.reminder_hours_before)
        
        # Rappels pour les étudiants inscrits
        enrolled_students = Enrollment.objects.filter(
            course=schedule.course,
            is_active=True
        ).select_related('student')
        
        for enrollment in enrolled_students:
            EventReminder.objects.get_or_create(
                event=None,
                user=enrollment.student,
                reminder_type='email',
                defaults={
                    'scheduled_send_time': reminder_time,
                    'subject': f"Rappel de cours: {schedule.course.title}",
                    'message': cls._format_schedule_message(schedule, for_student=True)
                }
            )
        
        # Rappel pour l'instructeur
        EventReminder.objects.get_or_create(
            event=None,
            user=schedule.course.instructor,
            reminder_type='email',
            defaults={
                'scheduled_send_time': reminder_time,
                'subject': f"Rappel de cours: {schedule.course.title}",
                'message': cls._format_schedule_message(schedule, for_student=False)
            }
        )
    
    @classmethod
    def _format_event_message(cls, event):
        """Formate le message de rappel d'événement"""
        message = f"Rappel: {event.title}\n\n"
        message += f"Date: {event.start_date.strftime('%d/%m/%Y à %H:%M')}\n"
        message += f"Durée: {event.duration_minutes} minutes\n"
        
        if event.description:
            message += f"Description: {event.description}\n"
        
        if event.location:
            message += f"Lieu: {event.location}\n"
        
        if event.online_link:
            message += f"Lien: {event.online_link}\n"
        
        message += f"\n---\neSchool Platform"
        return message
    
    @classmethod
    def _format_schedule_message(cls, schedule, for_student=True):
        """Formate le message de rappel de cours"""
        if for_student:
            message = f"Rappel: Vous avez un cours prévu\n\n"
        else:
            message = f"Rappel: Vous devez donner un cours\n\n"
        
        message += f"Cours: {schedule.course.title}\n"
        message += f"Type: {schedule.get_schedule_type_display()}\n"
        message += f"Date: {schedule.scheduled_date.strftime('%d/%m/%Y à %H:%M')}\n"
        message += f"Durée: {schedule.duration_minutes} minutes\n"
        
        if not for_student:
            message += f"Étudiants inscrits: {schedule.get_enrolled_count()}\n"
        else:
            message += f"Instructeur: {schedule.course.instructor.get_full_name() or schedule.course.instructor.username}\n"
        
        if schedule.access_link:
            message += f"\nLien d'accès: {schedule.access_link}\n"
        
        if schedule.meeting_id:
            message += f"ID de réunion: {schedule.meeting_id}\n"
        
        if schedule.access_code:
            message += f"Code d'accès: {schedule.access_code}\n"
        
        if schedule.notes:
            message += f"\nNotes: {schedule.notes}\n"
        
        message += f"\n---\neSchool Platform"
        return message

class CalendarSyncService:
    """Service pour synchroniser les cours avec le calendrier"""
    
    @classmethod
    def sync_course_enrollments(cls, user):
        """Synchronise les inscriptions de cours avec le calendrier utilisateur"""
        from courses.models import Enrollment
        
        # Obtenir les cours auxquels l'utilisateur est inscrit
        enrollments = Enrollment.objects.filter(
            student=user,
            is_active=True
        ).select_related('course')
        
        # Créer des événements pour les cours qui n'en ont pas
        for enrollment in enrollments:
            course = enrollment.course
            
            # Vérifier s'il existe déjà des événements pour ce cours
            existing_events = Event.objects.filter(
                organizer=course.instructor,
                participants=user,
                title__icontains=course.title
            ).exists()
            
            if not existing_events:
                # Créer un événement générique pour le cours
                cls._create_course_event(course, user)
    
    @classmethod
    def sync_instructor_courses(cls, instructor):
        """Synchronise les cours d'un instructeur avec son calendrier"""
        from courses.models import Course
        
        courses = Course.objects.filter(
            instructor=instructor,
            is_published=True
        )
        
        for course in courses:
            # Vérifier s'il existe des planifications pour ce cours
            schedules = CourseSchedule.objects.filter(course=course)
            
            if not schedules.exists():
                # Créer une planification par défaut
                cls._create_default_schedule(course)
    
    @classmethod
    def _create_course_event(cls, course, student):
        """Crée un événement générique pour un cours"""
        # Calculer une date de début (par exemple, dans une semaine)
        start_date = timezone.now() + timedelta(days=7)
        end_date = start_date + timedelta(hours=2)  # Durée par défaut de 2h
        
        event = Event.objects.create(
            title=f"Cours: {course.title}",
            description=f"Cours inscrit: {course.description[:200]}...",
            event_type='course',
            start_date=start_date,
            end_date=end_date,
            organizer=course.instructor,
            color='#28a745',  # Vert pour les cours
            is_public=False,
            reminder_enabled=True,
            reminder_minutes_before=30
        )
        
        # Ajouter l'étudiant comme participant
        event.participants.add(student)
        
        return event
    
    @classmethod
    def _create_default_schedule(cls, course):
        """Crée une planification par défaut pour un cours"""
        # Planifier le cours pour la semaine prochaine
        scheduled_date = timezone.now() + timedelta(days=7)
        scheduled_date = scheduled_date.replace(hour=14, minute=0, second=0, microsecond=0)
        
        schedule = CourseSchedule.objects.create(
            course=course,
            schedule_type='live',
            scheduled_date=scheduled_date,
            duration_minutes=120,  # 2 heures par défaut
            auto_reminder=True,
            reminder_hours_before=24,
            notes=f"Cours en direct: {course.title}"
        )
        
        # Ajouter tous les étudiants inscrits
        enrolled_students = Enrollment.objects.filter(
            course=course,
            is_active=True
        ).values_list('student', flat=True)
        
        schedule.enrolled_students.set(enrolled_students)
        
        return schedule

class NotificationService:
    """Service pour les notifications en temps réel"""
    
    @classmethod
    def send_upcoming_events_notification(cls, user, hours_ahead=2):
        """Envoie une notification pour les événements à venir"""
        now = timezone.now()
        upcoming_time = now + timedelta(hours=hours_ahead)
        
        # Événements à venir
        upcoming_events = Event.objects.filter(
            participants=user,
            start_date__gte=now,
            start_date__lte=upcoming_time,
            is_active=True
        )
        
        # Cours à venir
        enrolled_courses = Enrollment.objects.filter(
            student=user,
            is_active=True
        ).values_list('course_id', flat=True)
        
        upcoming_schedules = CourseSchedule.objects.filter(
            course_id__in=enrolled_courses,
            scheduled_date__gte=now,
            scheduled_date__lte=upcoming_time
        ).select_related('course')
        
        notifications = []
        
        for event in upcoming_events:
            notifications.append({
                'type': 'event',
                'title': event.title,
                'start_time': event.start_date,
                'message': f"Votre événement '{event.title}' commence dans {cls._time_until(event.start_date, now)}"
            })
        
        for schedule in upcoming_schedules:
            notifications.append({
                'type': 'course',
                'title': schedule.course.title,
                'start_time': schedule.scheduled_date,
                'message': f"Le cours '{schedule.course.title}' commence dans {cls._time_until(schedule.scheduled_date, now)}"
            })
        
        return sorted(notifications, key=lambda x: x['start_time'])
    
    @classmethod
    def _time_until(cls, future_time, current_time):
        """Calcule le temps restant jusqu'à un événement"""
        delta = future_time - current_time
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        
        if hours > 0:
            return f"{hours}h{minutes:02d}"
        else:
            return f"{minutes} minutes"