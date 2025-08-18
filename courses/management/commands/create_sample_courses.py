from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from courses.models import Category, Course, Tag, Module, Lesson, LessonResource
from users.models import User


class Command(BaseCommand):
    help = 'Crée des données de test pour les cours'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-existing',
            action='store_true',
            help='Supprime les données existantes avant de créer les nouvelles',
        )
    
    def handle(self, *args, **options):
        if options['delete_existing']:
            self.stdout.write('Suppression des données existantes...')
            Course.objects.all().delete()
            Category.objects.all().delete()
            Tag.objects.all().delete()
        
        # Créer ou récupérer un instructeur
        instructor, created = User.objects.get_or_create(
            username='prof_demo',
            defaults={
                'email': 'prof@eschool.com',
                'first_name': 'Jean',
                'last_name': 'Dupont',
                'role': 'instructor',
                'is_active': True,
            }
        )
        if created:
            instructor.set_password('demo123')
            instructor.save()
            self.stdout.write(f'✅ Instructeur créé: {instructor.username}')
        
        # Créer les catégories
        categories_data = [
            {
                'name': 'Programmation',
                'description': 'Cours de programmation et développement',
                'icon': 'bi-code-slash',
                'color': '#007bff'
            },
            {
                'name': 'Web Development',
                'description': 'Développement web frontend et backend',
                'icon': 'bi-globe',
                'color': '#28a745',
                'parent': 'Programmation'
            },
            {
                'name': 'Data Science',
                'description': 'Science des données et intelligence artificielle',
                'icon': 'bi-graph-up',
                'color': '#ffc107'
            },
            {
                'name': 'Design',
                'description': 'Design graphique et UX/UI',
                'icon': 'bi-palette',
                'color': '#dc3545'
            }
        ]
        
        categories = {}
        for cat_data in categories_data:
            parent = None
            if 'parent' in cat_data:
                parent = categories.get(cat_data.pop('parent'))
            
            category, created = Category.objects.get_or_create(
                name=cat_data['name'],
                defaults={**cat_data, 'parent': parent}
            )
            categories[category.name] = category
            if created:
                self.stdout.write(f'✅ Catégorie créée: {category.name}')
        
        # Créer les tags
        tags_data = [
            ('Python', '#3776ab'),
            ('JavaScript', '#f7df1e'),
            ('React', '#61dafb'),
            ('Django', '#092e20'),
            ('HTML', '#e34f26'),
            ('CSS', '#1572b6'),
            ('API', '#6c757d'),
            ('Database', '#336791'),
        ]
        
        tags = {}
        for tag_name, color in tags_data:
            tag, created = Tag.objects.get_or_create(
                name=tag_name,
                defaults={'color': color}
            )
            tags[tag_name] = tag
            if created:
                self.stdout.write(f'✅ Tag créé: {tag.name}')
        
        # Créer les cours
        courses_data = [
            {
                'title': 'Introduction au Python',
                'description': 'Apprenez les bases du langage Python de manière progressive et pratique. Ce cours vous accompagnera depuis les concepts fondamentaux jusqu\'aux applications avancées.',
                'short_description': 'Maîtrisez Python depuis les bases jusqu\'aux concepts avancés',
                'category': categories['Programmation'],
                'difficulty': 'beginner',
                'is_free': True,
                'estimated_duration': timedelta(hours=20),
                'learning_objectives': '• Comprendre la syntaxe Python\n• Créer vos premiers programmes\n• Manipuler les structures de données\n• Gérer les fichiers et les erreurs',
                'prerequisites': 'Aucune expérience en programmation requise',
                'target_audience': 'Débutants souhaitant apprendre la programmation',
                'status': 'published',
                'tags': ['Python'],
                'modules': [
                    {
                        'title': 'Les fondamentaux',
                        'description': 'Variables, types de données, opérateurs',
                        'lessons': [
                            {
                                'title': 'Introduction à Python',
                                'content': 'Python est un langage de programmation puissant et facile à apprendre...',
                                'lesson_type': 'text',
                                'duration': timedelta(minutes=30)
                            },
                            {
                                'title': 'Variables et types de données',
                                'content': 'Les variables permettent de stocker des informations...',
                                'lesson_type': 'text',
                                'duration': timedelta(minutes=45)
                            }
                        ]
                    },
                    {
                        'title': 'Structures de contrôle',
                        'description': 'Conditions, boucles et fonctions',
                        'lessons': [
                            {
                                'title': 'Les conditions if/else',
                                'content': 'Les conditions permettent d\'exécuter du code selon certains critères...',
                                'lesson_type': 'text',
                                'duration': timedelta(minutes=40)
                            }
                        ]
                    }
                ]
            },
            {
                'title': 'Développement Web avec React',
                'description': 'Créez des applications web modernes et interactives avec React. Apprenez les concepts clés et les meilleures pratiques.',
                'short_description': 'Développez des applications web modernes avec React',
                'category': categories['Web Development'],
                'difficulty': 'intermediate',
                'is_free': False,
                'price': 49.99,
                'estimated_duration': timedelta(hours=35),
                'learning_objectives': '• Maîtriser les composants React\n• Gérer l\'état des applications\n• Intégrer des APIs\n• Déployer vos applications',
                'prerequisites': 'Bases de JavaScript et HTML/CSS',
                'target_audience': 'Développeurs web intermédiaires',
                'status': 'published',
                'is_featured': True,
                'tags': ['JavaScript', 'React', 'HTML', 'CSS'],
                'modules': [
                    {
                        'title': 'Introduction à React',
                        'description': 'Concepts de base et premier composant',
                        'lessons': [
                            {
                                'title': 'Qu\'est-ce que React ?',
                                'content': 'React est une bibliothèque JavaScript pour créer des interfaces utilisateur...',
                                'lesson_type': 'text',
                                'duration': timedelta(minutes=25)
                            }
                        ]
                    }
                ]
            },
            {
                'title': 'API REST avec Django',
                'description': 'Concevez et développez des APIs REST robustes avec Django REST Framework.',
                'short_description': 'Créez des APIs REST professionnelles avec Django',
                'category': categories['Web Development'],
                'difficulty': 'advanced',
                'is_free': False,
                'price': 79.99,
                'estimated_duration': timedelta(hours=25),
                'learning_objectives': '• Concevoir des APIs REST\n• Implémenter l\'authentification\n• Gérer les permissions\n• Documenter vos APIs',
                'prerequisites': 'Expérience avec Python et Django',
                'target_audience': 'Développeurs Python avancés',
                'status': 'published',
                'tags': ['Python', 'Django', 'API'],
                'modules': [
                    {
                        'title': 'Fondamentaux des APIs REST',
                        'description': 'Principes REST et configuration Django',
                        'lessons': [
                            {
                                'title': 'Principes REST',
                                'content': 'REST (Representational State Transfer) est un style d\'architecture...',
                                'lesson_type': 'text',
                                'duration': timedelta(minutes=35)
                            }
                        ]
                    }
                ]
            }
        ]
        
        # Créer les cours avec leurs modules et leçons
        for course_data in courses_data:
            tags_list = course_data.pop('tags', [])
            modules_data = course_data.pop('modules', [])
            
            course, created = Course.objects.get_or_create(
                title=course_data['title'],
                defaults={
                    **course_data,
                    'instructor': instructor,
                    'publish_date': timezone.now() if course_data.get('status') == 'published' else None
                }
            )
            
            if created:
                # Ajouter les tags
                for tag_name in tags_list:
                    if tag_name in tags:
                        course.tags.add(tags[tag_name])
                
                # Créer les modules et leçons
                for module_order, module_data in enumerate(modules_data, 1):
                    lessons_data = module_data.pop('lessons', [])
                    
                    module = Module.objects.create(
                        course=course,
                        order=module_order,
                        is_published=True,
                        **module_data
                    )
                    
                    for lesson_order, lesson_data in enumerate(lessons_data, 1):
                        Lesson.objects.create(
                            module=module,
                            order=lesson_order,
                            is_published=True,
                            **lesson_data
                        )
                
                self.stdout.write(f'✅ Cours créé: {course.title}')
        
        # Afficher les statistiques
        self.stdout.write(f'\n📊 Statistiques:')
        self.stdout.write(f'   - Catégories: {Category.objects.count()}')
        self.stdout.write(f'   - Tags: {Tag.objects.count()}')
        self.stdout.write(f'   - Cours: {Course.objects.count()}')
        self.stdout.write(f'   - Modules: {Module.objects.count()}')
        self.stdout.write(f'   - Leçons: {Lesson.objects.count()}')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Données de test créées avec succès!'))