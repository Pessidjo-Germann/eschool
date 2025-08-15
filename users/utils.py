from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings

def send_verification_email(user, request):
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    # We get the domain from the request, but since we are in a backend environment,
    # we will hardcode it for now. In a real app, you would use:
    # from django.contrib.sites.shortcuts import get_current_site
    # current_site = get_current_site(request).domain
    current_site = "localhost:8000" # or your frontend URL

    verify_url = f"http://{current_site}/api/users/verify-email/{uid}/{token}/"

    subject = 'Activate Your Account'
    message = render_to_string('emails/verify_email.html', {
        'user': user,
        'verify_url': verify_url,
    })

    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])

def send_password_reset_email(user, request):
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    current_site = "localhost:8000" # or your frontend URL

    reset_url = f"http://{current_site}/api/users/password-reset-confirm/{uid}/{token}/"

    subject = 'Password Reset Request'
    message = render_to_string('emails/password_reset_email.html', {
        'user': user,
        'reset_url': reset_url,
    })

    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
