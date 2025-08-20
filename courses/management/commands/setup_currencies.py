"""
Commande Django pour configurer les devises de base
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from courses.models import Currency


class Command(BaseCommand):
    help = 'Configure les devises de base pour la plateforme'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--update-rates',
            action='store_true',
            help='Met à jour les taux de change existants'
        )
    
    def handle(self, *args, **options):
        currencies_data = [
            {
                'code': 'XAF',
                'name': 'Franc CFA (BEAC)',
                'symbol': 'FCFA',
                'exchange_rate_to_base': 1.0000,
                'is_active': True
            },
            {
                'code': 'XOF',
                'name': 'Franc CFA (BCEAO)',
                'symbol': 'FCFA',
                'exchange_rate_to_base': 1.0000,  # Même valeur que XAF
                'is_active': True
            },
            {
                'code': 'EUR',
                'name': 'Euro',
                'symbol': '€',
                'exchange_rate_to_base': 655.96,  # 1 EUR = ~656 XAF
                'is_active': True
            },
            {
                'code': 'USD',
                'name': 'Dollar américain',
                'symbol': '$',
                'exchange_rate_to_base': 600.00,  # 1 USD = ~600 XAF
                'is_active': True
            },
            {
                'code': 'CAD',
                'name': 'Dollar canadien',
                'symbol': 'CAD$',
                'exchange_rate_to_base': 450.00,  # 1 CAD = ~450 XAF
                'is_active': True
            },
            {
                'code': 'GBP',
                'name': 'Livre sterling',
                'symbol': '£',
                'exchange_rate_to_base': 750.00,  # 1 GBP = ~750 XAF
                'is_active': True
            },
            {
                'code': 'CHF',
                'name': 'Franc suisse',
                'symbol': 'CHF',
                'exchange_rate_to_base': 650.00,  # 1 CHF = ~650 XAF
                'is_active': False  # Pas activé par défaut
            },
            {
                'code': 'JPY',
                'name': 'Yen japonais',
                'symbol': '¥',
                'exchange_rate_to_base': 4.50,  # 1 JPY = ~4.5 XAF
                'is_active': False  # Pas activé par défaut
            }
        ]
        
        with transaction.atomic():
            created_count = 0
            updated_count = 0
            
            for currency_data in currencies_data:
                currency, created = Currency.objects.get_or_create(
                    code=currency_data['code'],
                    defaults=currency_data
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Devise créée: {currency_data["code"]} - {currency_data["name"]}'
                        )
                    )
                elif options['update_rates']:
                    # Mettre à jour le taux de change
                    currency.exchange_rate_to_base = currency_data['exchange_rate_to_base']
                    currency.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'Taux mis à jour: {currency_data["code"]} = {currency_data["exchange_rate_to_base"]}'
                        )
                    )
            
            # Résumé
            self.stdout.write('\n' + '='*50)
            self.stdout.write(f'Devises créées: {created_count}')
            self.stdout.write(f'Devises mises à jour: {updated_count}')
            self.stdout.write(f'Total devises: {Currency.objects.count()}')
            
            # Afficher les devises actives
            active_currencies = Currency.objects.filter(is_active=True)
            self.stdout.write('\nDevises actives:')
            for curr in active_currencies:
                self.stdout.write(f'  - {curr.code}: {curr.name} (1 {curr.code} = {curr.exchange_rate_to_base} XAF)')
            
            self.stdout.write(
                self.style.SUCCESS('\n✅ Configuration des devises terminée!')
            )
        
        # Conseils d'utilisation
        self.stdout.write('\n' + '='*50)
        self.stdout.write('CONSEILS D\'UTILISATION:')
        self.stdout.write('1. Les taux de change sont indicatifs et doivent être mis à jour régulièrement')
        self.stdout.write('2. Utilisez --update-rates pour mettre à jour les taux existants')
        self.stdout.write('3. XAF est la devise de base (taux = 1.0000)')
        self.stdout.write('4. Activez/désactivez les devises depuis l\'admin Django')