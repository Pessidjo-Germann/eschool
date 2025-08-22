from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from django.template.loader import render_to_string
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import qrcode
import logging
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfutils
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.units import inch

from .models import Certificate, CertificateTemplate

logger = logging.getLogger(__name__)


class CertificateGeneratorService:
    """Service pour la génération automatique de certificats"""
    
    # Dimensions standard pour les certificats (px)
    CERTIFICATE_WIDTH = 1920
    CERTIFICATE_HEIGHT = 1080
    
    # Police par défaut si aucune police personnalisée n'est trouvée
    DEFAULT_FONTS = {
        'title': 'DejaVuSans-Bold.ttf',
        'name': 'DejaVuSans-Bold.ttf',
        'course': 'DejaVuSans.ttf',
        'text': 'DejaVuSans.ttf',
    }
    
    def __init__(self):
        self.setup_fonts()
    
    def setup_fonts(self):
        """Configure les polices disponibles"""
        try:
            # Répertoire des polices du système
            font_paths = [
                '/usr/share/fonts/truetype/liberation/',
                '/usr/share/fonts/truetype/dejavu/',
                '/System/Library/Fonts/',
                'C:/Windows/Fonts/',
            ]
            
            self.available_fonts = {}
            
            # Charger les polices disponibles
            for font_path in font_paths:
                font_dir = Path(font_path)
                if font_dir.exists():
                    for font_file in font_dir.glob('*.ttf'):
                        try:
                            font_name = font_file.stem
                            self.available_fonts[font_name] = str(font_file)
                        except Exception as e:
                            logger.warning(f"Impossible de charger la police {font_file}: {e}")
                            
        except Exception as e:
            logger.warning(f"Erreur lors du chargement des polices: {e}")
            self.available_fonts = {}
    
    def get_font_path(self, font_type='text'):
        """Obtient le chemin d'une police"""
        default_font = self.DEFAULT_FONTS.get(font_type, 'DejaVuSans.ttf')
        
        # Cherche d'abord la police par défaut
        if default_font.replace('.ttf', '') in self.available_fonts:
            return self.available_fonts[default_font.replace('.ttf', '')]
        
        # Fallback vers n'importe quelle police disponible
        if self.available_fonts:
            return next(iter(self.available_fonts.values()))
        
        # Dernier recours: police système
        return None
    
    def generate_certificate_for_enrollment(self, enrollment):
        """Génère un certificat pour une inscription complétée"""
        try:
            # Vérifier si l'inscription est éligible
            if not self.is_eligible_for_certificate(enrollment):
                logger.warning(f"Inscription {enrollment.id} non éligible pour un certificat")
                return None
            
            # Vérifier si un certificat existe déjà
            existing_certificate = Certificate.objects.filter(enrollment=enrollment).first()
            if existing_certificate:
                logger.info(f"Certificat existant trouvé: {existing_certificate.certificate_number}")
                return existing_certificate
            
            # Obtenir le template approprié
            template = self.get_appropriate_template(enrollment)
            if not template:
                logger.error("Aucun template de certificat disponible")
                return None
            
            # Créer le certificat
            certificate = Certificate.objects.create(
                user=enrollment.user,
                course=enrollment.course,
                enrollment=enrollment,
                template=template,
                completion_date=enrollment.completed_at or timezone.now(),
                final_grade=getattr(enrollment, 'final_grade', None),
                completion_percentage=getattr(enrollment, 'completion_percentage', 100.0),
                duration_hours=getattr(enrollment, 'total_study_hours', None),
            )
            
            # Générer le fichier image du certificat
            self.generate_certificate_image(certificate)
            
            # Générer le PDF
            self.generate_certificate_pdf(certificate)
            
            # Générer le QR code
            self.generate_qr_code(certificate)
            
            # Marquer comme généré
            certificate.mark_as_generated()
            certificate.mark_as_issued()
            
            logger.info(f"Certificat généré avec succès: {certificate.certificate_number}")
            return certificate
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du certificat: {e}")
            return None
    
    def is_eligible_for_certificate(self, enrollment):
        """Vérifie si une inscription est éligible pour un certificat"""
        # L'inscription doit être complétée
        if enrollment.status != 'completed':
            return False
        
        # Le cours doit être publié
        if enrollment.course.status != 'published':
            return False
        
        # L'inscription doit avoir une date de completion
        if not enrollment.completed_at:
            return False
        
        return True
    
    def get_appropriate_template(self, enrollment):
        """Sélectionne le template approprié pour l'inscription"""
        # Logique de sélection basée sur la performance
        final_grade = getattr(enrollment, 'final_grade', None)
        
        if final_grade and final_grade >= 85:
            # Template pour les excellents résultats
            template = CertificateTemplate.objects.filter(
                template_type='achievement',
                is_active=True
            ).first()
            if template:
                return template
        
        # Template par défaut pour la completion
        template = CertificateTemplate.objects.filter(
            template_type='completion',
            is_default=True,
            is_active=True
        ).first()
        
        if not template:
            # N'importe quel template actif
            template = CertificateTemplate.objects.filter(
                is_active=True
            ).first()
        
        return template
    
    def generate_certificate_image(self, certificate):
        """Génère l'image du certificat"""
        try:
            template = certificate.template
            
            # Créer l'image de base
            if template.background_image:
                # Utiliser l'image de fond
                img = Image.open(template.background_image.path)
                img = img.resize((self.CERTIFICATE_WIDTH, self.CERTIFICATE_HEIGHT), Image.Resampling.LANCZOS)
            else:
                # Créer une image avec couleur de fond
                img = Image.new('RGB', (self.CERTIFICATE_WIDTH, self.CERTIFICATE_HEIGHT), 
                              template.background_color)
            
            draw = ImageDraw.Draw(img)
            
            # Ajouter la bordure
            if template.border_width > 0:
                border_color = template.border_color
                for i in range(template.border_width):
                    draw.rectangle(
                        [i, i, self.CERTIFICATE_WIDTH-1-i, self.CERTIFICATE_HEIGHT-1-i],
                        outline=border_color
                    )
            
            # Ajouter le logo si présent
            if template.logo:
                try:
                    logo = Image.open(template.logo.path)
                    logo = logo.resize((200, 200), Image.Resampling.LANCZOS)
                    # Positionner le logo en haut à gauche
                    img.paste(logo, (100, 100))
                except Exception as e:
                    logger.warning(f"Impossible d'ajouter le logo: {e}")
            
            # Ajouter les textes
            self.add_text_to_certificate(draw, certificate, template)
            
            # Sauvegarder l'image
            image_buffer = BytesIO()
            img.save(image_buffer, format='PNG', quality=95)
            image_buffer.seek(0)
            
            filename = f"certificate_{certificate.certificate_number}.png"
            certificate.certificate_file.save(
                filename,
                ContentFile(image_buffer.getvalue()),
                save=True
            )
            
            logger.info(f"Image du certificat générée: {filename}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération de l'image: {e}")
            raise
    
    def add_text_to_certificate(self, draw, certificate, template):
        """Ajoute les textes au certificat"""
        try:
            # Titre principal
            title_font = self.get_font(template.title_font_size)
            title_bbox = draw.textbbox((0, 0), template.title_text, font=title_font)
            title_width = title_bbox[2] - title_bbox[0]
            title_x = (self.CERTIFICATE_WIDTH - title_width) // 2
            draw.text((title_x, 200), template.title_text, 
                     fill=template.title_color, font=title_font)
            
            # Sous-titre
            if template.subtitle_text:
                subtitle_font = self.get_font(24)
                subtitle_bbox = draw.textbbox((0, 0), template.subtitle_text, font=subtitle_font)
                subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
                subtitle_x = (self.CERTIFICATE_WIDTH - subtitle_width) // 2
                draw.text((subtitle_x, 280), template.subtitle_text, 
                         fill=template.title_color, font=subtitle_font)
            
            # Nom du récipiendaire
            name_font = self.get_font(template.name_font_size)
            name_bbox = draw.textbbox((0, 0), certificate.recipient_name, font=name_font)
            name_width = name_bbox[2] - name_bbox[0]
            name_x = (self.CERTIFICATE_WIDTH - name_width) // 2
            draw.text((name_x, 380), certificate.recipient_name, 
                     fill=template.name_color, font=name_font)
            
            # Texte de completion
            completion_font = self.get_font(24)
            completion_bbox = draw.textbbox((0, 0), template.completion_text, font=completion_font)
            completion_width = completion_bbox[2] - completion_bbox[0]
            completion_x = (self.CERTIFICATE_WIDTH - completion_width) // 2
            draw.text((completion_x, 480), template.completion_text, 
                     fill=template.course_color, font=completion_font)
            
            # Nom du cours
            course_font = self.get_font(template.course_font_size)
            course_bbox = draw.textbbox((0, 0), certificate.course_title, font=course_font)
            course_width = course_bbox[2] - course_bbox[0]
            course_x = (self.CERTIFICATE_WIDTH - course_width) // 2
            draw.text((course_x, 550), certificate.course_title, 
                     fill=template.course_color, font=course_font)
            
            # Note finale si présente
            if certificate.final_grade:
                grade_text = f"Note finale: {certificate.display_grade}"
                grade_font = self.get_font(20)
                grade_bbox = draw.textbbox((0, 0), grade_text, font=grade_font)
                grade_width = grade_bbox[2] - grade_bbox[0]
                grade_x = (self.CERTIFICATE_WIDTH - grade_width) // 2
                draw.text((grade_x, 650), grade_text, 
                         fill=template.course_color, font=grade_font)
            
            # Date de completion
            date_text = f"Complété le {certificate.completion_date.strftime('%d/%m/%Y')}"
            date_font = self.get_font(18)
            draw.text((200, self.CERTIFICATE_HEIGHT - 200), date_text, 
                     fill=template.course_color, font=date_font)
            
            # Signature
            signature_font = self.get_font(18)
            draw.text((self.CERTIFICATE_WIDTH - 400, self.CERTIFICATE_HEIGHT - 200), 
                     template.signature_text, 
                     fill=template.course_color, font=signature_font)
            
            # Numéro de certificat
            number_text = f"Certificat N° {certificate.certificate_number}"
            number_font = self.get_font(14)
            draw.text((200, self.CERTIFICATE_HEIGHT - 100), number_text, 
                     fill=template.course_color, font=number_font)
            
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout du texte: {e}")
            raise
    
    def get_font(self, size):
        """Obtient une police de la taille spécifiée"""
        try:
            font_path = self.get_font_path()
            if font_path:
                return ImageFont.truetype(font_path, size)
        except Exception:
            pass
        
        # Fallback vers la police par défaut
        try:
            return ImageFont.load_default()
        except Exception:
            return None
    
    def generate_certificate_pdf(self, certificate):
        """Génère la version PDF du certificat"""
        try:
            buffer = BytesIO()
            p = canvas.Canvas(buffer, pagesize=landscape(A4))
            
            template = certificate.template
            
            # Configuration de la page
            width, height = landscape(A4)
            
            # Couleur de fond
            if template.background_color != '#ffffff':
                p.setFillColor(HexColor(template.background_color))
                p.rect(0, 0, width, height, fill=1)
            
            # Bordure
            if template.border_width > 0:
                p.setStrokeColor(HexColor(template.border_color))
                p.setLineWidth(template.border_width)
                p.rect(20, 20, width-40, height-40)
            
            # Titre
            p.setFillColor(HexColor(template.title_color))
            p.setFont("Helvetica-Bold", min(template.title_font_size, 36))
            title_width = p.stringWidth(template.title_text, "Helvetica-Bold", 
                                       min(template.title_font_size, 36))
            p.drawString((width - title_width) / 2, height - 150, template.title_text)
            
            # Sous-titre
            if template.subtitle_text:
                p.setFont("Helvetica", 16)
                subtitle_width = p.stringWidth(template.subtitle_text, "Helvetica", 16)
                p.drawString((width - subtitle_width) / 2, height - 200, template.subtitle_text)
            
            # Nom du récipiendaire
            p.setFillColor(HexColor(template.name_color))
            p.setFont("Helvetica-Bold", min(template.name_font_size, 32))
            name_width = p.stringWidth(certificate.recipient_name, "Helvetica-Bold", 
                                      min(template.name_font_size, 32))
            p.drawString((width - name_width) / 2, height - 280, certificate.recipient_name)
            
            # Texte de completion
            p.setFillColor(HexColor(template.course_color))
            p.setFont("Helvetica", 14)
            completion_width = p.stringWidth(template.completion_text, "Helvetica", 14)
            p.drawString((width - completion_width) / 2, height - 330, template.completion_text)
            
            # Titre du cours
            p.setFont("Helvetica-Bold", min(template.course_font_size, 24))
            course_width = p.stringWidth(certificate.course_title, "Helvetica-Bold", 
                                        min(template.course_font_size, 24))
            p.drawString((width - course_width) / 2, height - 380, certificate.course_title)
            
            # Note finale
            if certificate.final_grade:
                grade_text = f"Note finale: {certificate.display_grade}"
                p.setFont("Helvetica", 12)
                grade_width = p.stringWidth(grade_text, "Helvetica", 12)
                p.drawString((width - grade_width) / 2, height - 430, grade_text)
            
            # Date et signature
            p.setFont("Helvetica", 10)
            date_text = f"Complété le {certificate.completion_date.strftime('%d/%m/%Y')}"
            p.drawString(50, 100, date_text)
            p.drawString(width - 200, 100, template.signature_text)
            
            # Numéro de certificat
            p.setFont("Helvetica", 8)
            p.drawString(50, 50, f"Certificat N° {certificate.certificate_number}")
            
            p.showPage()
            p.save()
            
            # Sauvegarder le PDF
            buffer.seek(0)
            filename = f"certificate_{certificate.certificate_number}.pdf"
            certificate.pdf_file.save(
                filename,
                ContentFile(buffer.getvalue()),
                save=True
            )
            
            logger.info(f"PDF du certificat généré: {filename}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du PDF: {e}")
            raise
    
    def generate_qr_code(self, certificate):
        """Génère le code QR de vérification"""
        try:
            verification_url = f"{settings.SITE_URL}{certificate.get_verification_url()}"
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(verification_url)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Sauvegarder le QR code
            qr_buffer = BytesIO()
            img.save(qr_buffer, format='PNG')
            qr_buffer.seek(0)
            
            filename = f"qr_{certificate.certificate_number}.png"
            certificate.qr_code.save(
                filename,
                ContentFile(qr_buffer.getvalue()),
                save=True
            )
            
            logger.info(f"QR code généré: {filename}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du QR code: {e}")


# Service singleton
certificate_generator = CertificateGeneratorService()