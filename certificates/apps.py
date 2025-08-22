from django.apps import AppConfig


class CertificatesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "certificates"
    verbose_name = "Certificats"
    
    def ready(self):
        """Importe les signaux quand l'application est prête"""
        import certificates.signals
