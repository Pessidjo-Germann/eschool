from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
from scheduler.models import Event, CourseSchedule, EventReminder
from courses.models import Enrollment

class Command(BaseCommand):
    help = 'Envoie les rappels d\'événements et de cours programmés'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulation sans envoi réel des rappels',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()
        
        # Statistiques
        events_processed = 0
        schedules_processed = 0
        reminders_sent = 0
        
        self.stdout.write(f"Traitement des rappels à {now}")
        
        # 1. Rappels d'événements personnels
        upcoming_events = Event.objects.filter(
            is_active=True,
            reminder_enabled=True,
            start_date__gt=now,
            start_date__lte=now + timedelta(days=1)  # Événements dans les 24h
        )
        
        for event in upcoming_events:
            reminder_time = event.start_date - timedelta(minutes=event.reminder_minutes_before)
            
            if now >= reminder_time:
                # Vérifier si le rappel n'a pas déjà été envoyé
                existing_reminder = EventReminder.objects.filter(
                    event=event,
                    user=event.organizer,
                    reminder_type='email' if event.email_reminder else 'in_app'
                ).first()
                
                if not existing_reminder:
                    # Créer le rappel
                    reminder = EventReminder.objects.create(
                        event=event,
                        user=event.organizer,
                        reminder_type='email' if event.email_reminder else 'in_app',
                        scheduled_send_time=reminder_time,
                        subject=f"Rappel: {event.title}",
                        message=self.format_event_reminder(event)
                    )
                    
                    if not dry_run:
                        self.send_reminder(reminder)
                    
                    reminders_sent += 1
                    self.stdout.write(f"  Rappel envoyé pour: {event.title}")
                    
                # Traiter les participants
                for participant in event.participants.all():
                    existing_participant_reminder = EventReminder.objects.filter(
                        event=event,
                        user=participant,
                        reminder_type='email' if event.email_reminder else 'in_app'
                    ).first()
                    
                    if not existing_participant_reminder:
                        participant_reminder = EventReminder.objects.create(
                            event=event,
                            user=participant,
                            reminder_type='email' if event.email_reminder else 'in_app',
                            scheduled_send_time=reminder_time,
                            subject=f"Rappel: {event.title}",
                            message=self.format_event_reminder(event)
                        )
                        
                        if not dry_run:
                            self.send_reminder(participant_reminder)
                        
                        reminders_sent += 1
            
            events_processed += 1
        
        # 2. Rappels de cours planifiés
        upcoming_schedules = CourseSchedule.objects.filter(
            auto_reminder=True,
            reminder_sent=False,
            scheduled_date__gt=now,
            scheduled_date__lte=now + timedelta(days=2)  # Cours dans les 48h
        ).select_related('course')
        
        for schedule in upcoming_schedules:
            reminder_time = schedule.scheduled_date - timedelta(hours=schedule.reminder_hours_before)
            
            if now >= reminder_time:
                # Obtenir tous les étudiants inscrits
                enrolled_students = Enrollment.objects.filter(
                    course=schedule.course,
                    is_active=True
                ).select_related('student')
                
                # Envoyer les rappels aux étudiants
                for enrollment in enrolled_students:
                    student = enrollment.student
                    
                    # Vérifier si le rappel existe déjà
                    existing_reminder = EventReminder.objects.filter(
                        event=None,  # Pas d'événement lié
                        user=student,
                        reminder_type='email'
                    ).filter(
                        message__contains=str(schedule.id)
                    ).first()
                    
                    if not existing_reminder:
                        reminder = EventReminder.objects.create(
                            event=None,
                            user=student,
                            reminder_type='email',
                            scheduled_send_time=reminder_time,
                            actual_send_time=now if not dry_run else None,
                            subject=f"Rappel de cours: {schedule.course.title}",
                            message=self.format_schedule_reminder(schedule)
                        )
                        
                        if not dry_run:
                            self.send_schedule_reminder(reminder, schedule)
                        
                        reminders_sent += 1
                
                # Rappel pour l'instructeur
                instructor_reminder = EventReminder.objects.create(
                    event=None,
                    user=schedule.course.instructor,
                    reminder_type='email',
                    scheduled_send_time=reminder_time,
                    actual_send_time=now if not dry_run else None,
                    subject=f"Rappel de cours à donner: {schedule.course.title}",
                    message=self.format_instructor_reminder(schedule)
                )
                
                if not dry_run:
                    self.send_schedule_reminder(instructor_reminder, schedule)
                    schedule.reminder_sent = True
                    schedule.save()
                
                reminders_sent += 1
                self.stdout.write(f"  Rappels de cours envoyés pour: {schedule.course.title}")
            
            schedules_processed += 1
        
        # Résumé
        self.stdout.write(
            self.style.SUCCESS(
                f"\nRésumé {'(SIMULATION)' if dry_run else ''}:\n"
                f"  Événements traités: {events_processed}\n"
                f"  Cours traités: {schedules_processed}\n"
                f"  Rappels envoyés: {reminders_sent}"
            )
        )

    def format_event_reminder(self, event):
        """Format le message de rappel pour un événement"""
        message = f"Rappel: Vous avez un événement prévu\n\n"
        message += f"Titre: {event.title}\n"
        message += f"Date: {event.start_date.strftime('%d/%m/%Y à %H:%M')}\n"
        
        if event.description:
            message += f"Description: {event.description}\n"
        
        if event.location:
            message += f"Lieu: {event.location}\n"
        
        if event.online_link:
            message += f"Lien: {event.online_link}\n"
        
        message += f"\n---\nenvoyé par eSchool Platform"
        return message

    def format_schedule_reminder(self, schedule):
        """Format le message de rappel pour un cours planifié"""
        message = f"Rappel: Vous avez un cours prévu\n\n"
        message += f"Cours: {schedule.course.title}\n"
        message += f"Type: {schedule.get_schedule_type_display()}\n"
        message += f"Date: {schedule.scheduled_date.strftime('%d/%m/%Y à %H:%M')}\n"
        message += f"Durée: {schedule.duration_minutes} minutes\n"
        message += f"Instructeur: {schedule.course.instructor.get_full_name() or schedule.course.instructor.username}\n"
        
        if schedule.access_link:
            message += f"\nLien d'accès: {schedule.access_link}\n"
        
        if schedule.meeting_id:
            message += f"ID de réunion: {schedule.meeting_id}\n"
        
        if schedule.access_code:
            message += f"Code d'accès: {schedule.access_code}\n"
        
        if schedule.notes:
            message += f"\nNotes: {schedule.notes}\n"
        
        message += f"\n---\nRappel automatique eSchool - ID: {schedule.id}"
        return message

    def format_instructor_reminder(self, schedule):
        """Format le message de rappel pour l'instructeur"""
        message = f"Rappel: Vous devez donner un cours\n\n"
        message += f"Cours: {schedule.course.title}\n"
        message += f"Type: {schedule.get_schedule_type_display()}\n"
        message += f"Date: {schedule.scheduled_date.strftime('%d/%m/%Y à %H:%M')}\n"
        message += f"Durée prévue: {schedule.duration_minutes} minutes\n"
        message += f"Étudiants inscrits: {schedule.get_enrolled_count()}\n"
        
        if schedule.access_link:
            message += f"\nLien d'accès: {schedule.access_link}\n"
        
        if schedule.notes:
            message += f"\nVos notes: {schedule.notes}\n"
        
        message += f"\n---\nRappel automatique eSchool - ID: {schedule.id}"
        return message

    def send_reminder(self, reminder):
        """Envoie un rappel d'événement"""
        try:
            if reminder.reminder_type == 'email':
                send_mail(
                    subject=reminder.subject,
                    message=reminder.message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[reminder.user.email],
                    fail_silently=False
                )
            
            reminder.status = 'sent'
            reminder.actual_send_time = timezone.now()
            reminder.save()
            
        except Exception as e:
            reminder.status = 'failed'
            reminder.error_message = str(e)
            reminder.save()
            self.stdout.write(
                self.style.ERROR(f"Erreur envoi rappel à {reminder.user.email}: {e}")
            )

    def send_schedule_reminder(self, reminder, schedule):
        """Envoie un rappel de cours planifié"""
        try:
            send_mail(
                subject=reminder.subject,
                message=reminder.message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[reminder.user.email],
                fail_silently=False
            )
            
            reminder.status = 'sent'
            reminder.save()
            
        except Exception as e:
            reminder.status = 'failed'
            reminder.error_message = str(e)
            reminder.save()
            self.stdout.write(
                self.style.ERROR(f"Erreur envoi rappel cours à {reminder.user.email}: {e}")
            )