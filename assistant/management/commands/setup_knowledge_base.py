from django.core.management.base import BaseCommand
from assistant.models import KnowledgeBase, AssistantConfiguration


class Command(BaseCommand):
    help = 'Initialise la base de connaissances avec des FAQ de base'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Initialisation de la base de connaissances...'))
        
        # Données de base pour la FAQ
        knowledge_entries = [
            # Questions générales
            {
                'category': 'general',
                'title': 'Qu\'est-ce que cette plateforme?',
                'question': 'Qu\'est-ce que cette plateforme d\'e-learning?',
                'answer': 'Cette plateforme est un système d\'apprentissage en ligne intelligent qui vous permet de suivre des cours, passer des évaluations, obtenir des certificats et interagir avec des instructeurs expérimentés. Nous offrons des formations dans différents domaines avec un suivi personnalisé de votre progression.',
                'keywords': 'plateforme, e-learning, apprentissage, système, formation, cours en ligne',
                'priority': 10
            },
            {
                'category': 'general',
                'title': 'Comment fonctionne la plateforme?',
                'question': 'Comment utiliser la plateforme?',
                'answer': 'Pour utiliser la plateforme: 1) Créez votre compte, 2) Parcourez les cours disponibles, 3) Inscrivez-vous aux cours qui vous intéressent, 4) Suivez les modules à votre rythme, 5) Passez les évaluations, 6) Obtenez votre certificat de réussite.',
                'keywords': 'utilisation, fonctionnement, étapes, guide, démarrer',
                'priority': 9
            },
            
            # Questions sur les cours
            {
                'category': 'courses',
                'title': 'Types de cours disponibles',
                'question': 'Quels types de cours proposez-vous?',
                'answer': 'Nous proposons des cours dans plusieurs domaines: développement web, programmation, design, marketing digital, gestion de projet, langues, et bien d\'autres. Chaque cours comprend des vidéos, des exercices pratiques, des quiz et un support d\'instructeur.',
                'keywords': 'types cours, domaines, développement, programmation, design, marketing',
                'priority': 8
            },
            {
                'category': 'courses',
                'title': 'Durée des cours',
                'question': 'Combien de temps durent les cours?',
                'answer': 'La durée varie selon le cours. Les cours courts durent 2-5 heures, les cours intermédiaires 10-20 heures, et les formations complètes peuvent aller jusqu\'à 50+ heures. Vous apprenez à votre propre rythme.',
                'keywords': 'durée, temps, heures, rythme, formation',
                'priority': 7
            },
            {
                'category': 'courses',
                'title': 'Prérequis pour les cours',
                'question': 'Y a-t-il des prérequis pour suivre les cours?',
                'answer': 'Chaque cours indique clairement ses prérequis. Les cours débutants ne nécessitent aucune connaissance préalable, tandis que les cours avancés peuvent demander des bases dans le domaine. Vérifiez la description du cours pour connaître le niveau requis.',
                'keywords': 'prérequis, niveau, débutant, avancé, connaissances',
                'priority': 6
            },
            
            # Questions sur les paiements
            {
                'category': 'payments',
                'title': 'Méthodes de paiement acceptées',
                'question': 'Quelles sont les méthodes de paiement acceptées?',
                'answer': 'Nous acceptons les paiements par Mobile Money (MTN Money, Orange Money), cartes bancaires (Visa, Mastercard), et virements bancaires. Tous les paiements sont sécurisés et chiffrés.',
                'keywords': 'paiement, mobile money, MTN, Orange Money, carte bancaire, virement',
                'priority': 9
            },
            {
                'category': 'payments',
                'title': 'Sécurité des paiements',
                'question': 'Les paiements sont-ils sécurisés?',
                'answer': 'Oui, tous nos paiements utilisent un chiffrement SSL 256-bit et sont traités par des partenaires de paiement certifiés. Nous ne stockons jamais vos informations bancaires. Vos données financières sont entièrement protégées.',
                'keywords': 'sécurité, SSL, chiffrement, protection, données bancaires',
                'priority': 8
            },
            {
                'category': 'payments',
                'title': 'Politique de remboursement',
                'question': 'Puis-je obtenir un remboursement?',
                'answer': 'Nous offrons une garantie de remboursement de 30 jours si vous n\'êtes pas satisfait du cours. Le remboursement est possible si vous avez suivi moins de 20% du contenu. Contactez notre support pour initier un remboursement.',
                'keywords': 'remboursement, garantie, 30 jours, satisfaction, politique',
                'priority': 7
            },
            
            # Questions sur l'inscription
            {
                'category': 'enrollment',
                'title': 'Comment s\'inscrire à un cours',
                'question': 'Comment m\'inscrire à un cours?',
                'answer': 'Pour vous inscrire: 1) Connectez-vous à votre compte, 2) Trouvez le cours souhaité, 3) Cliquez sur "S\'inscrire" ou "Acheter maintenant", 4) Choisissez votre méthode de paiement, 5) Finalisez le paiement. Vous aurez immédiatement accès au cours.',
                'keywords': 'inscription, s\'inscrire, étapes, paiement, accès',
                'priority': 9
            },
            {
                'category': 'enrollment',
                'title': 'Accès après inscription',
                'question': 'Combien de temps ai-je accès au cours après inscription?',
                'answer': 'Une fois inscrit, vous avez un accès à vie au cours. Vous pouvez le suivre à votre rythme, revenir sur les modules, et accéder aux mises à jour futures du contenu.',
                'keywords': 'accès, durée, à vie, permanent, mises à jour',
                'priority': 8
            },
            
            # Questions sur le compte
            {
                'category': 'account',
                'title': 'Création de compte',
                'question': 'Comment créer un compte?',
                'answer': 'Cliquez sur "S\'inscrire" en haut de la page, remplissez le formulaire avec votre email, nom et mot de passe. Vous recevrez un email de confirmation. Une fois confirmé, votre compte sera actif.',
                'keywords': 'compte, inscription, créer, email, confirmation',
                'priority': 8
            },
            {
                'category': 'account',
                'title': 'Récupération de mot de passe',
                'question': 'J\'ai oublié mon mot de passe, que faire?',
                'answer': 'Cliquez sur "Mot de passe oublié" sur la page de connexion, entrez votre email, et suivez les instructions dans l\'email que vous recevrez pour réinitialiser votre mot de passe.',
                'keywords': 'mot de passe, oublié, récupération, réinitialiser, email',
                'priority': 7
            },
            
            # Questions techniques
            {
                'category': 'technical',
                'title': 'Problèmes de connexion',
                'question': 'Je n\'arrive pas à me connecter, que faire?',
                'answer': 'Vérifiez que votre email et mot de passe sont corrects. Assurez-vous que votre compte est confirmé. Si le problème persiste, effacez le cache de votre navigateur ou contactez notre support technique.',
                'keywords': 'connexion, problème, email, mot de passe, cache, support',
                'priority': 6
            },
            {
                'category': 'technical',
                'title': 'Compatibilité navigateur',
                'question': 'Quels navigateurs sont compatibles?',
                'answer': 'La plateforme fonctionne sur tous les navigateurs modernes: Chrome, Firefox, Safari, Edge. Nous recommandons d\'utiliser la dernière version de votre navigateur pour une expérience optimale.',
                'keywords': 'navigateur, compatibilité, Chrome, Firefox, Safari, Edge',
                'priority': 5
            },
            
            # Questions sur les certificats
            {
                'category': 'certificates',
                'title': 'Obtention des certificats',
                'question': 'Comment obtenir un certificat?',
                'answer': 'Vous obtenez automatiquement un certificat après avoir: 1) Terminé tous les modules du cours, 2) Réussi tous les quiz avec au moins 70%, 3) Complété le projet final si requis. Le certificat est téléchargeable en PDF.',
                'keywords': 'certificat, obtenir, modules, quiz, 70%, projet final, PDF',
                'priority': 8
            },
            {
                'category': 'certificates',
                'title': 'Validité des certificats',
                'question': 'Les certificats sont-ils reconnus?',
                'answer': 'Nos certificats attestent de votre réussite et des compétences acquises. Ils sont acceptés par de nombreuses entreprises et peuvent valoriser votre CV. Ils incluent un code de vérification unique.',
                'keywords': 'certificat, reconnu, entreprise, CV, vérification, compétences',
                'priority': 7
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for entry_data in knowledge_entries:
            entry, created = KnowledgeBase.objects.get_or_create(
                title=entry_data['title'],
                defaults=entry_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(f'✓ Créé: {entry.title}')
            else:
                # Mettre à jour si nécessaire
                updated = False
                for field, value in entry_data.items():
                    if field != 'title' and getattr(entry, field) != value:
                        setattr(entry, field, value)
                        updated = True
                
                if updated:
                    entry.save()
                    updated_count += 1
                    self.stdout.write(f'↻ Mis à jour: {entry.title}')
        
        # Créer une configuration d'assistant de base si elle n'existe pas
        config, config_created = AssistantConfiguration.objects.get_or_create(
            name='default',
            defaults={
                'api_key': 'YOUR_GEMINI_API_KEY_HERE',
                'model': 'gemini-1.5-flash',
                'max_tokens': 1000,
                'temperature': 0.7,
                'is_active': True,
                'enable_knowledge_base': True,
                'enable_context_memory': True,
                'max_context_messages': 10
            }
        )
        
        if config_created:
            self.stdout.write(f'✓ Configuration d\'assistant créée: {config.name}')
        
        # Résumé
        self.stdout.write(self.style.SUCCESS(f'''
Base de connaissances initialisée avec succès!
- {created_count} nouvelles entrées créées
- {updated_count} entrées mises à jour
- Configuration assistant: {"créée" if config_created else "existante"}

Pour utiliser l'assistant:
1. Obtenez une clé API Gemini sur https://aistudio.google.com/app/apikey
2. Allez dans l'admin Django > Assistant > Configurations Assistant
3. Modifiez la configuration "default" et ajoutez votre vraie clé API
4. L'assistant sera alors opérationnel!
        '''))