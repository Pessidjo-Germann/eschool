from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from certificates.models import CertificateTemplate

User = get_user_model()


class Command(BaseCommand):
    help = 'Crée les templates de certificats par défaut'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force la recréation des templates existants',
        )

    def handle(self, *args, **options):
        force = options['force']
        
        # Template de completion par défaut
        completion_template, created = CertificateTemplate.objects.get_or_create(
            name="Template de Completion Standard",
            template_type='completion',
            defaults={
                'is_default': True,
                'is_active': True,
                'background_color': '#ffffff',
                'border_color': '#2c3e50',
                'border_width': 8,
                'title_text': 'CERTIFICAT DE COMPLETION',
                'subtitle_text': 'est décerné à',
                'completion_text': 'pour avoir complété avec succès le cours',
                'signature_text': 'Équipe pédagogique eSchool',
                'title_font_size': 48,
                'name_font_size': 36,
                'course_font_size': 28,
                'title_color': '#2c3e50',
                'name_color': '#e74c3c',
                'course_color': '#34495e',
            }
        )
        
        if created or force:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Template de completion créé: {completion_template.name}')
            )
        else:
            self.stdout.write(f'- Template de completion existe déjà: {completion_template.name}')
        
        # Template d'excellence
        excellence_template, created = CertificateTemplate.objects.get_or_create(
            name="Template d'Excellence",
            template_type='achievement',
            defaults={
                'is_default': True,
                'is_active': True,
                'background_color': '#f8f9fa',
                'border_color': '#f39c12',
                'border_width': 10,
                'title_text': 'CERTIFICAT D\'EXCELLENCE',
                'subtitle_text': 'est décerné avec distinction à',
                'completion_text': 'pour son excellence dans le cours',
                'signature_text': 'Direction académique eSchool',
                'title_font_size': 52,
                'name_font_size': 40,
                'course_font_size': 32,
                'title_color': '#c0392b',
                'name_color': '#f39c12',
                'course_color': '#2c3e50',
            }
        )
        
        if created or force:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Template d\'excellence créé: {excellence_template.name}')
            )
        else:
            self.stdout.write(f'- Template d\'excellence existe déjà: {excellence_template.name}')
        
        # Template de participation
        participation_template, created = CertificateTemplate.objects.get_or_create(
            name="Template de Participation",
            template_type='participation',
            defaults={
                'is_default': True,
                'is_active': True,
                'background_color': '#ecf0f1',
                'border_color': '#3498db',
                'border_width': 5,
                'title_text': 'CERTIFICAT DE PARTICIPATION',
                'subtitle_text': 'est décerné à',
                'completion_text': 'pour sa participation active au cours',
                'signature_text': 'Équipe eSchool',
                'title_font_size': 44,
                'name_font_size': 34,
                'course_font_size': 26,
                'title_color': '#3498db',
                'name_color': '#2c3e50',
                'course_color': '#7f8c8d',
            }
        )
        
        if created or force:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Template de participation créé: {participation_template.name}')
            )
        else:
            self.stdout.write(f'- Template de participation existe déjà: {participation_template.name}')
        
        self.stdout.write(
            self.style.SUCCESS('\n🎉 Configuration des templates terminée !')
        )