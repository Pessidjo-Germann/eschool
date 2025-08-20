"""
Commande Django pour configurer les niveaux de tarification géographique
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from courses.models import PricingTier


class Command(BaseCommand):
    help = 'Configure les niveaux de tarification géographique'
    
    def handle(self, *args, **options):
        pricing_tiers_data = [
            {
                'name': 'Afrique Centrale',
                'description': 'Tarification adaptée aux pays d\'Afrique Centrale',
                'countries': ['CM', 'GA', 'GQ', 'CF', 'TD', 'CG'],
                'discount_percentage': 0.00,  # Prix normal
                'is_active': True
            },
            {
                'name': 'Afrique de l\'Ouest',
                'description': 'Tarification pour les pays francophones d\'Afrique de l\'Ouest',
                'countries': ['SN', 'CI', 'BF', 'ML', 'NE', 'GN', 'TG', 'BJ'],
                'discount_percentage': 5.00,  # 5% de réduction
                'is_active': True
            },
            {
                'name': 'Maghreb',
                'description': 'Pays du Maghreb avec pouvoir d\'achat différent',
                'countries': ['MA', 'DZ', 'TN', 'LY'],
                'discount_percentage': 10.00,  # 10% de réduction
                'is_active': True
            },
            {
                'name': 'Afrique Anglophone',
                'description': 'Pays anglophones d\'Afrique',
                'countries': ['NG', 'GH', 'KE', 'UG', 'TZ', 'ZA', 'ZW', 'ZM'],
                'discount_percentage': 15.00,  # 15% de réduction
                'is_active': True
            },
            {
                'name': 'Autres pays africains',
                'description': 'Autres pays d\'Afrique avec économies en développement',
                'countries': ['MG', 'MW', 'MZ', 'AO', 'ET', 'RW', 'BI'],
                'discount_percentage': 20.00,  # 20% de réduction
                'is_active': True
            },
            {
                'name': 'Étudiants Europe/Amérique',
                'description': 'Tarification spéciale pour étudiants des pays développés',
                'countries': ['FR', 'BE', 'CH', 'CA', 'US'],
                'discount_percentage': 25.00,  # 25% de réduction pour étudiants
                'is_active': False  # À activer manuellement avec vérification statut étudiant
            }
        ]
        
        with transaction.atomic():
            created_count = 0
            
            for tier_data in pricing_tiers_data:
                tier, created = PricingTier.objects.get_or_create(
                    name=tier_data['name'],
                    defaults=tier_data
                )
                
                if created:
                    created_count += 1
                    countries_str = ', '.join(tier_data['countries'])
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Niveau créé: {tier_data["name"]} ({tier_data["discount_percentage"]}% réduction)'
                        )
                    )
                    self.stdout.write(f'  Pays: {countries_str}')
            
            # Résumé
            self.stdout.write('\n' + '='*60)
            self.stdout.write(f'Niveaux de tarification créés: {created_count}')
            self.stdout.write(f'Total niveaux: {PricingTier.objects.count()}')
            
            # Afficher les niveaux actifs
            active_tiers = PricingTier.objects.filter(is_active=True).order_by('discount_percentage')
            self.stdout.write('\nNiveaux de tarification actifs:')
            for tier in active_tiers:
                countries_display = ', '.join(tier.countries) if tier.countries else 'Aucun pays'
                self.stdout.write(
                    f'  - {tier.name}: {tier.discount_percentage}% de réduction'
                )
                self.stdout.write(f'    Pays: {countries_display}')
            
            self.stdout.write(
                self.style.SUCCESS('\n✅ Configuration des niveaux de tarification terminée!')
            )
        
        # Conseils d'utilisation
        self.stdout.write('\n' + '='*60)
        self.stdout.write('CONSEILS D\'UTILISATION:')
        self.stdout.write('1. Les réductions sont appliquées automatiquement selon le pays de l\'utilisateur')
        self.stdout.write('2. Configurez le pays dans le profil utilisateur pour activer les réductions')
        self.stdout.write('3. Les pourcentages peuvent être ajustés dans l\'admin Django')
        self.stdout.write('4. Un utilisateur peut bénéficier du premier niveau qui correspond à son pays')
        self.stdout.write('5. Le niveau "Étudiants Europe/Amérique" nécessite une validation manuelle')
        
        # Informations techniques
        self.stdout.write('\n' + '='*60)
        self.stdout.write('INFORMATIONS TECHNIQUES:')
        self.stdout.write('- Les codes pays utilisent le format ISO 3166-1 alpha-2')
        self.stdout.write('- La logique de réduction est dans pricing_services.py')
        self.stdout.write('- Les réductions se cumulent avec les codes promo si autorisé')