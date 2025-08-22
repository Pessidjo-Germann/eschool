from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from certificates.models import Certificate, CertificateTemplate
from certificates.services import certificate_generator
from courses.models import Course, Enrollment

User = get_user_model()


class Command(BaseCommand):
    help = 'Génère des certificats de test pour démonstration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=5,
            help='Nombre de certificats de test à créer',
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Username de l\'utilisateur pour les certificats',
        )

    def handle(self, *args, **options):
        count = options['count']
        username = options.get('user')
        
        # Obtenir ou créer un utilisateur de test
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Utilisateur {username} non trouvé')
                )
                return
        else:
            user, created = User.objects.get_or_create(
                username='testuser',
                defaults={
                    'first_name': 'Jean',
                    'last_name': 'Dupont',
                    'email': 'test@eschool.com',
                }
            )
            if created:
                user.set_password('testpass123')
                user.save()
                self.stdout.write(f'✓ Utilisateur de test créé: {user.username}')
        
        # Vérifier qu'il y a des templates
        templates = CertificateTemplate.objects.filter(is_active=True)
        if not templates.exists():
            self.stdout.write(
                self.style.WARNING('Aucun template trouvé. Création des templates par défaut...')
            )
            from django.core.management import call_command
            call_command('create_default_certificate_template')
            templates = CertificateTemplate.objects.filter(is_active=True)
        
        # Créer un instructeur de test si nécessaire
        instructor, created = User.objects.get_or_create(
            username='instructor_test',
            defaults={
                'first_name': 'Marie',
                'last_name': 'Professeur',
                'email': 'prof@eschool.com',
                'role': 'instructor',
            }
        )
        if created:
            instructor.set_password('testpass123')
            instructor.save()
            self.stdout.write(f'✓ Instructeur de test créé: {instructor.username}')
        
        # Obtenir ou créer des cours de test
        test_courses = []
        course_data = [
            {'title': 'Introduction à Python', 'slug': 'intro-python'},
            {'title': 'Développement Web avec Django', 'slug': 'django-web'},
            {'title': 'Data Science avec Pandas', 'slug': 'data-science-pandas'},
            {'title': 'Intelligence Artificielle', 'slug': 'ai-fundamentals'},
            {'title': 'Marketing Digital', 'slug': 'digital-marketing'},
        ]
        
        for course_info in course_data[:count]:
            course, created = Course.objects.get_or_create(
                slug=course_info['slug'],
                defaults={
                    'title': course_info['title'],
                    'description': f'Cours de test: {course_info["title"]}',
                    'status': 'published',
                    'is_free': True,
                    'instructor': instructor,
                }
            )
            test_courses.append(course)
            if created:
                self.stdout.write(f'✓ Cours de test créé: {course.title}')
        
        # Créer des inscriptions et certificats de test
        certificates_created = 0
        for i, course in enumerate(test_courses):
            # Créer une inscription complétée
            enrollment, created = Enrollment.objects.get_or_create(
                user=user,
                course=course,
                defaults={
                    'status': 'completed',
                    'completed_at': timezone.now(),
                    'progress_percentage': 100.0,
                }
            )
            
            if created or not hasattr(enrollment, 'certificate'):
                enrollment.status = 'completed'
                enrollment.completed_at = timezone.now()
                enrollment.save()
                
                # Sélectionner un template en fonction de la note
                grade = 60 + (i * 8)  # Notes entre 60 et 100
                if grade >= 85:
                    template = templates.filter(template_type='achievement').first()
                elif grade >= 50:
                    template = templates.filter(template_type='completion').first()
                else:
                    template = templates.filter(template_type='participation').first()
                
                if not template:
                    template = templates.first()
                
                # Créer le certificat manuellement pour le test
                certificate = Certificate.objects.create(
                    user=user,
                    course=course,
                    enrollment=enrollment,
                    template=template,
                    final_grade=grade,
                    completion_percentage=100.0,
                    recipient_name=user.get_full_name() or user.username,
                    course_title=course.title,
                    completion_date=timezone.now(),
                )
                
                # Générer les fichiers
                try:
                    certificate_generator.generate_certificate_image(certificate)
                    certificate_generator.generate_certificate_pdf(certificate)
                    certificate_generator.generate_qr_code(certificate)
                    
                    certificate.mark_as_generated()
                    certificate.mark_as_issued()
                    
                    certificates_created += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Certificat créé: {certificate.certificate_number} '
                            f'({course.title}, Note: {grade}%)'
                        )
                    )
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'✗ Erreur lors de la génération du certificat pour {course.title}: {e}'
                        )
                    )
            else:
                self.stdout.write(f'- Certificat existe déjà pour {course.title}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎉 {certificates_created} certificat(s) de test créé(s) pour {user.username} !'
            )
        )
        
        if certificates_created > 0:
            self.stdout.write(
                f'\n📝 Vous pouvez voir les certificats à: /certificates/'
            )