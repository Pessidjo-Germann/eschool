"""
Services pour la gestion des factures, génération PDF et envoi emails
"""
import io
import os
from datetime import date, datetime
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.platypus.flowables import HRFlowable
from .models import Invoice, PaymentTransaction
import logging

logger = logging.getLogger(__name__)


class InvoiceGenerator:
    """Générateur de factures PDF"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
    
    def setup_custom_styles(self):
        """Configurer les styles personnalisés"""
        # Style pour le titre
        self.styles.add(ParagraphStyle(
            name='InvoiceTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=20,
            alignment=1  # Center
        ))
        
        # Style pour les en-têtes de section
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#34495e'),
            spaceBefore=15,
            spaceAfter=10,
            leftIndent=0
        ))
        
        # Style pour le contenu
        self.styles.add(ParagraphStyle(
            name='InvoiceContent',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=6
        ))
        
        # Style pour les totaux
        self.styles.add(ParagraphStyle(
            name='TotalAmount',
            parent=self.styles['Normal'],
            fontSize=14,
            textColor=colors.HexColor('#27ae60'),
            spaceBefore=10,
            alignment=2  # Right
        ))
    
    def generate_invoice_pdf(self, invoice: Invoice) -> bytes:
        """
        Générer le PDF d'une facture
        
        Args:
            invoice: Instance de facture
            
        Returns:
            bytes: Contenu du PDF généré
        """
        try:
            # Créer un buffer pour le PDF
            buffer = io.BytesIO()
            
            # Créer le document PDF
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )
            
            # Construire le contenu
            story = []
            
            # En-tête avec logo (si disponible)
            story.extend(self._build_header(invoice))
            
            # Informations de la facture
            story.extend(self._build_invoice_info(invoice))
            
            # Informations de facturation et société
            story.extend(self._build_billing_info(invoice))
            
            # Détails des articles/services
            story.extend(self._build_items_table(invoice))
            
            # Totaux
            story.extend(self._build_totals(invoice))
            
            # Notes et conditions
            story.extend(self._build_footer(invoice))
            
            # Générer le PDF
            doc.build(story)
            
            # Récupérer le contenu
            buffer.seek(0)
            pdf_content = buffer.read()
            buffer.close()
            
            logger.info(f"PDF généré avec succès pour la facture {invoice.invoice_number}")
            return pdf_content
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du PDF pour {invoice.invoice_number}: {e}")
            raise
    
    def _build_header(self, invoice: Invoice) -> list:
        """Construire l'en-tête de la facture"""
        story = []
        
        # Titre
        story.append(Paragraph("FACTURE", self.styles['InvoiceTitle']))
        story.append(Spacer(1, 20))
        
        # Informations de l'entreprise (à gauche) et facture (à droite)
        company_info = [
            ["<b>eSchool Platform</b>", f"<b>Facture N°:</b> {invoice.invoice_number}"],
            ["Plateforme d'apprentissage en ligne", f"<b>Date d'émission:</b> {invoice.issue_date.strftime('%d/%m/%Y')}"],
            ["Douala, Cameroun", f"<b>Date d'échéance:</b> {invoice.due_date.strftime('%d/%m/%Y')}"],
            ["Email: contact@eschool.com", f"<b>Statut:</b> {invoice.get_status_display()}"],
            ["Tél: +237 123 456 789", ""]
        ]
        
        header_table = Table(company_info, colWidths=[3*inch, 3*inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#34495e')),
        ]))
        
        story.append(header_table)
        story.append(Spacer(1, 30))
        
        return story
    
    def _build_invoice_info(self, invoice: Invoice) -> list:
        """Construire les informations de la facture"""
        story = []
        
        # Ligne de séparation
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#bdc3c7')))
        story.append(Spacer(1, 20))
        
        return story
    
    def _build_billing_info(self, invoice: Invoice) -> list:
        """Construire les informations de facturation"""
        story = []
        
        story.append(Paragraph("Informations de facturation", self.styles['SectionHeader']))
        
        billing_data = [
            [f"<b>Nom:</b> {invoice.billing_name}"],
            [f"<b>Email:</b> {invoice.billing_email}"],
        ]
        
        if invoice.billing_phone:
            billing_data.append([f"<b>Téléphone:</b> {invoice.billing_phone}"])
        
        if invoice.billing_address:
            billing_data.append([f"<b>Adresse:</b> {invoice.billing_address}"])
        
        if invoice.billing_city:
            billing_data.append([f"<b>Ville:</b> {invoice.billing_city}, {invoice.billing_country}"])
        
        billing_table = Table(billing_data, colWidths=[6*inch])
        billing_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        story.append(billing_table)
        story.append(Spacer(1, 20))
        
        return story
    
    def _build_items_table(self, invoice: Invoice) -> list:
        """Construire le tableau des articles/services"""
        story = []
        
        story.append(Paragraph("Détails de la commande", self.styles['SectionHeader']))
        
        # En-têtes du tableau
        headers = ['Description', 'Quantité', 'Prix unitaire', 'Total']
        
        # Données du tableau
        transaction = invoice.transaction
        description = transaction.description
        if transaction.content_type and transaction.content_type.model == 'course':
            try:
                from courses.models import Course
                course = Course.objects.get(id=transaction.object_id)
                description = f"Inscription au cours: {course.title}"
            except:
                pass
        
        data = [
            headers,
            [
                description,
                '1',
                f"{invoice.subtotal:,.0f} {invoice.currency}",
                f"{invoice.subtotal:,.0f} {invoice.currency}"
            ]
        ]
        
        items_table = Table(data, colWidths=[3*inch, 0.8*inch, 1.2*inch, 1.2*inch])
        items_table.setStyle(TableStyle([
            # Style de l'en-tête
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (1, 0), (-1, 0), 'CENTER'),
            
            # Style du contenu
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#2c3e50')),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
            
            # Bordures
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
            
            # Alternance de couleurs
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            
            # Padding
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        story.append(items_table)
        story.append(Spacer(1, 20))
        
        return story
    
    def _build_totals(self, invoice: Invoice) -> list:
        """Construire la section des totaux"""
        story = []
        
        # Données des totaux
        totals_data = [
            ['Sous-total:', f"{invoice.subtotal:,.0f} {invoice.currency}"],
        ]
        
        if invoice.tax_amount > 0:
            totals_data.append([
                f'Taxes ({invoice.tax_rate*100:.1f}%):', 
                f"{invoice.tax_amount:,.0f} {invoice.currency}"
            ])
        
        totals_data.append([
            '<b>TOTAL À PAYER:</b>', 
            f"<b>{invoice.total_amount:,.0f} {invoice.currency}</b>"
        ])
        
        totals_table = Table(totals_data, colWidths=[4*inch, 2*inch], hAlign='RIGHT')
        totals_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -2), 10),
            ('FONTSIZE', (0, -1), (-1, -1), 12),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LINEBELOW', (0, -1), (-1, -1), 1, colors.HexColor('#27ae60')),
        ]))
        
        story.append(totals_table)
        story.append(Spacer(1, 30))
        
        return story
    
    def _build_footer(self, invoice: Invoice) -> list:
        """Construire le pied de page"""
        story = []
        
        # Notes
        if invoice.notes:
            story.append(Paragraph("Notes", self.styles['SectionHeader']))
            story.append(Paragraph(invoice.notes, self.styles['InvoiceContent']))
            story.append(Spacer(1, 15))
        
        # Conditions de paiement
        story.append(Paragraph("Conditions de paiement", self.styles['SectionHeader']))
        payment_terms = [
            "• Paiement dû sous 30 jours à compter de la date d'émission",
            "• Garantie satisfait ou remboursé sous 30 jours",
            "• Pour toute question, contactez-nous à support@eschool.com"
        ]
        
        for term in payment_terms:
            story.append(Paragraph(term, self.styles['InvoiceContent']))
        
        story.append(Spacer(1, 30))
        
        # Pied de page
        footer_text = "Merci de votre confiance ! - eSchool Platform"
        story.append(Paragraph(footer_text, self.styles['InvoiceContent']))
        
        return story


class InvoiceEmailService:
    """Service d'envoi d'emails pour les factures"""
    
    def __init__(self):
        self.from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@eschool.com')
    
    def send_invoice_email(self, invoice: Invoice, generate_pdf: bool = True) -> bool:
        """
        Envoyer une facture par email
        
        Args:
            invoice: Instance de facture
            generate_pdf: Si True, génère et attache le PDF
            
        Returns:
            bool: True si l'envoi a réussi
        """
        try:
            # Préparer le contenu de l'email
            subject = f"Facture {invoice.invoice_number} - eSchool"
            
            # Contexte pour le template
            context = {
                'invoice': invoice,
                'transaction': invoice.transaction,
                'user': invoice.user,
                'company_name': 'eSchool Platform',
            }
            
            # Générer le contenu HTML et texte
            html_content = render_to_string('emails/invoice_email.html', context)
            text_content = render_to_string('emails/invoice_email.txt', context)
            
            # Créer l'email
            email = EmailMessage(
                subject=subject,
                body=text_content,
                from_email=self.from_email,
                to=[invoice.billing_email],
                reply_to=[self.from_email],
            )
            
            # Ajouter la version HTML
            email.attach_alternative(html_content, "text/html")
            
            # Générer et attacher le PDF si demandé
            if generate_pdf:
                pdf_content = self._get_or_generate_pdf(invoice)
                if pdf_content:
                    email.attach(
                        f"facture_{invoice.invoice_number}.pdf",
                        pdf_content,
                        'application/pdf'
                    )
            
            # Envoyer l'email
            email.send()
            
            # Marquer comme envoyé
            invoice.mark_email_sent()
            
            logger.info(f"Email de facture envoyé avec succès: {invoice.invoice_number}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de l'email pour {invoice.invoice_number}: {e}")
            return False
    
    def _get_or_generate_pdf(self, invoice: Invoice) -> bytes:
        """Obtenir le PDF existant ou le générer"""
        try:
            # Vérifier si le PDF existe déjà
            if invoice.pdf_file and os.path.exists(invoice.pdf_file.path):
                with open(invoice.pdf_file.path, 'rb') as f:
                    return f.read()
            
            # Générer un nouveau PDF
            generator = InvoiceGenerator()
            pdf_content = generator.generate_invoice_pdf(invoice)
            
            # Sauvegarder le PDF
            pdf_file = ContentFile(pdf_content)
            invoice.pdf_file.save(
                f"facture_{invoice.invoice_number}.pdf",
                pdf_file,
                save=True
            )
            
            return pdf_content
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du PDF: {e}")
            return None


class InvoiceAutomationService:
    """Service d'automatisation pour les factures"""
    
    def __init__(self):
        self.generator = InvoiceGenerator()
        self.email_service = InvoiceEmailService()
    
    def create_invoice_for_transaction(self, transaction: PaymentTransaction) -> Invoice:
        """
        Créer automatiquement une facture pour une transaction
        
        Args:
            transaction: Transaction PaymentTransaction
            
        Returns:
            Invoice: Facture créée
        """
        try:
            # Vérifier si une facture existe déjà
            if hasattr(transaction, 'invoice'):
                return transaction.invoice
            
            # Créer la facture
            invoice = Invoice.objects.create(
                transaction=transaction,
                user=transaction.user,
                billing_name=transaction.customer_name,
                billing_email=transaction.customer_email,
                billing_phone=transaction.customer_phone or '',
                subtotal=transaction.amount,
                total_amount=transaction.amount,
                currency=transaction.currency,
                status='draft'
            )
            
            logger.info(f"Facture créée automatiquement: {invoice.invoice_number}")
            return invoice
            
        except Exception as e:
            logger.error(f"Erreur lors de la création de facture pour {transaction.reference}: {e}")
            raise
    
    def process_successful_transaction(self, transaction: PaymentTransaction):
        """
        Traiter une transaction réussie (créer facture et envoyer email)
        
        Args:
            transaction: Transaction réussie
        """
        try:
            # Créer ou obtenir la facture
            invoice = self.create_invoice_for_transaction(transaction)
            
            # Marquer comme payée
            invoice.mark_as_paid()
            
            # Générer le PDF
            pdf_content = self.generator.generate_invoice_pdf(invoice)
            pdf_file = ContentFile(pdf_content)
            invoice.pdf_file.save(
                f"facture_{invoice.invoice_number}.pdf",
                pdf_file,
                save=True
            )
            
            # Envoyer par email
            self.email_service.send_invoice_email(invoice, generate_pdf=False)  # PDF déjà généré
            
            logger.info(f"Transaction {transaction.reference} traitée avec succès")
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement de la transaction {transaction.reference}: {e}")


# Instances de service
invoice_generator = InvoiceGenerator()
invoice_email_service = InvoiceEmailService()
invoice_automation_service = InvoiceAutomationService()