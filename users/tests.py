from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .models import User
from django.core import mail
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

class UserAuthenticationTests(APITestCase):

    def setUp(self):
        self.register_url = reverse('users:register')
        self.login_url = reverse('token_obtain_pair')
        self.logout_url = reverse('users:logout')
        self.admin_only_url = reverse('users:admin-only')

        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'strong_password123',
            'password2': 'strong_password123',
            'first_name': 'Test',
            'last_name': 'User',
            'role': 'apprenant'
        }

        self.admin_data = {
            'username': 'adminuser',
            'email': 'admin@example.com',
            'password': 'strong_password123',
            'password2': 'strong_password123',
            'first_name': 'Admin',
            'last_name': 'User',
            'role': 'admin'
        }

    def test_user_registration(self):
        """
        Ensure we can register a new user.
        """
        response = self.client.post(self.register_url, self.user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)
        user = User.objects.get()
        self.assertEqual(user.username, self.user_data['username'])
        self.assertFalse(user.is_active) # Should be inactive until verified
        self.assertEqual(len(mail.outbox), 1) # Check that a verification email was sent
        self.assertEqual(mail.outbox[0].subject, 'Activate Your Account')

    def test_user_login(self):
        """
        Ensure a registered and verified user can log in.
        """
        # First, create and verify a user
        user = User.objects.create_user(**{k:v for k,v in self.user_data.items() if k not in ['password2']})
        user.is_active = True
        user.is_verified = True
        user.save()

        login_data = {'username': self.user_data['username'], 'password': self.user_data['password']}
        response = self.client.post(self.login_url, login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_user_logout(self):
        """
        Ensure a logged-in user can log out.
        """
        user = User.objects.create_user(**{k:v for k,v in self.user_data.items() if k not in ['password2']})
        user.is_active = True
        user.save()

        login_data = {'username': self.user_data['username'], 'password': self.user_data['password']}
        login_response = self.client.post(self.login_url, login_data, format='json')
        refresh_token = login_response.data['refresh']
        access_token = login_response.data['access']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        logout_response = self.client.post(self.logout_url, {'refresh': refresh_token}, format='json')

        self.assertEqual(logout_response.status_code, status.HTTP_205_RESET_CONTENT)

    def test_role_based_permissions(self):
        """
        Ensure role-based permissions are enforced.
        """
        # Create an admin and a regular user
        admin_user = User.objects.create_user(**{k:v for k,v in self.admin_data.items() if k not in ['password2']})
        admin_user.is_active = True
        admin_user.save()

        regular_user = User.objects.create_user(**{k:v for k,v in self.user_data.items() if k not in ['password2']})
        regular_user.is_active = True
        regular_user.save()

        # Admin should have access
        self.client.force_authenticate(user=admin_user)
        response = self.client.get(self.admin_only_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Regular user should not have access
        self.client.force_authenticate(user=regular_user)
        response = self.client.get(self.admin_only_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_password_reset_flow(self):
        """
        Ensure the password reset flow works correctly.
        """
        user = User.objects.create_user(**{k:v for k,v in self.user_data.items() if k not in ['password2']})

        # 1. Request password reset
        response = self.client.post(reverse('users:password-reset'), {'email': user.email}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Password Reset Request')

        # 2. Confirm password reset
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_url = reverse('users:password-reset-confirm', kwargs={'uidb64': uid, 'token': token})

        new_password = 'new_strong_password456'
        response = self.client.post(reset_url, {'password': new_password, 'password2': new_password}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 3. Verify new password works for login
        user.refresh_from_db()
        self.assertTrue(user.check_password(new_password))

        # Make user active to test login
        user.is_active = True
        user.save()

        login_data = {'username': user.username, 'password': new_password}
        response = self.client.post(self.login_url, login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
