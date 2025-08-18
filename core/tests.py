from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from core.forms import CustomUserCreationForm, CustomPasswordResetForm

User = get_user_model()


class UserModelTest(TestCase):
    """Test the custom User model"""
    
    def setUp(self):
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123',
            'first_name': 'Test',
            'last_name': 'User',
            'role': 'student'
        }
    
    def test_create_user_with_role(self):
        """Test creating a user with a specific role"""
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.role, 'student')
        self.assertTrue(user.is_student)
        self.assertFalse(user.is_instructor)
        self.assertFalse(user.is_admin)
        self.assertFalse(user.email_verified)
    
    def test_user_role_properties(self):
        """Test user role property methods"""
        # Test student
        student = User.objects.create_user(username='student', role='student')
        self.assertTrue(student.is_student)
        self.assertFalse(student.is_instructor)
        self.assertFalse(student.is_admin)
        
        # Test instructor
        instructor = User.objects.create_user(username='instructor', role='instructor')
        self.assertFalse(instructor.is_student)
        self.assertTrue(instructor.is_instructor)
        self.assertFalse(instructor.is_admin)
        
        # Test admin
        admin = User.objects.create_user(username='admin', role='admin')
        self.assertFalse(admin.is_student)
        self.assertFalse(admin.is_instructor)
        self.assertTrue(admin.is_admin)


class AuthenticationFormsTest(TestCase):
    """Test authentication forms"""
    
    def test_user_creation_form_valid(self):
        """Test valid user creation form"""
        form_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'role': 'instructor',
            'password1': 'complexpass123',
            'password2': 'complexpass123'
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_user_creation_form_email_required(self):
        """Test that email is required in user creation form"""
        form_data = {
            'username': 'newuser',
            'password1': 'complexpass123',
            'password2': 'complexpass123',
            'role': 'student'
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
    
    def test_user_creation_form_email_uniqueness(self):
        """Test email uniqueness validation"""
        # Create existing user
        User.objects.create_user(username='existing', email='existing@example.com')
        
        form_data = {
            'username': 'newuser',
            'email': 'existing@example.com',  # Same email
            'password1': 'complexpass123',
            'password2': 'complexpass123',
            'role': 'student'
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)


class AuthenticationViewsTest(TestCase):
    """Test authentication views"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='student'
        )
    
    def test_login_view_get(self):
        """Test login view GET request"""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Connexion')
    
    def test_login_view_post_valid(self):
        """Test login view POST with valid credentials"""
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after login
    
    def test_login_view_post_invalid(self):
        """Test login view POST with invalid credentials"""
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)  # Stay on login page
    
    def test_signup_view_get(self):
        """Test signup view GET request"""
        response = self.client.get(reverse('signup'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Créer votre compte')
    
    def test_signup_view_post_valid(self):
        """Test signup view POST with valid data"""
        response = self.client.post(reverse('signup'), {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'role': 'instructor',
            'password1': 'complexpass123',
            'password2': 'complexpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after signup
        self.assertTrue(User.objects.filter(username='newuser').exists())
    
    def test_logout_view(self):
        """Test logout view"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, 302)  # Redirect after logout
    
    def test_password_reset_view_get(self):
        """Test password reset view GET request"""
        response = self.client.get(reverse('password_reset'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mot de passe oublié')
    
    def test_password_reset_view_post(self):
        """Test password reset view POST request"""
        response = self.client.post(reverse('password_reset'), {
            'email': 'test@example.com'
        })
        self.assertEqual(response.status_code, 302)  # Redirect to done page
        # In testing, emails are stored in mail.outbox
        self.assertEqual(len(mail.outbox), 1)


class PermissionsTest(TestCase):
    """Test role-based permissions"""
    
    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            username='student', 
            email='student@example.com',
            password='testpass123',
            role='student'
        )
        self.instructor = User.objects.create_user(
            username='instructor',
            email='instructor@example.com', 
            password='testpass123',
            role='instructor'
        )
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='testpass123',
            role='admin'
        )
    
    def test_user_role_identification(self):
        """Test that user roles are correctly identified"""
        self.assertTrue(self.student.is_student)
        self.assertFalse(self.student.is_instructor)
        self.assertFalse(self.student.is_admin)
        
        self.assertFalse(self.instructor.is_student)
        self.assertTrue(self.instructor.is_instructor)
        self.assertFalse(self.instructor.is_admin)
        
        self.assertFalse(self.admin.is_student)
        self.assertFalse(self.admin.is_instructor)
        self.assertTrue(self.admin.is_admin)


class EmailVerificationTest(TestCase):
    """Test email verification functionality"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='student'
        )
        self.user.email_verified = False
        self.user.save()
    
    def test_email_verification_view(self):
        """Test email verification view"""
        token = self.user.email_verification_token
        response = self.client.get(reverse('verify_email', args=[token]))
        self.assertEqual(response.status_code, 302)  # Redirect after verification
        
        # Check that user is now verified
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)
    
    def test_invalid_email_verification_token(self):
        """Test email verification with invalid token"""
        import uuid
        invalid_token = uuid.uuid4()
        response = self.client.get(reverse('verify_email', args=[invalid_token]))
        self.assertEqual(response.status_code, 302)  # Redirect to home
        
        # Check that user is still not verified
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)
