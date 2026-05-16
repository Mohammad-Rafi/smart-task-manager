"""
Smart Task Manager - Test Suite
Unit tests for models, forms, views, and API.
"""

from datetime import date, timedelta

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from .models import Category, Task, TaskAttachment, TaskActivity
from .forms import TaskForm, CategoryForm, SignUpForm


# =============================================================================
# MODEL TESTS
# =============================================================================

class CategoryModelTest(TestCase):
    """Test Category model behavior."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_category_creation(self):
        """Test basic category creation."""
        cat = Category.objects.create(
            user=self.user,
            name='Work',
            color='#64ffda'
        )
        self.assertEqual(cat.name, 'Work')
        self.assertEqual(cat.slug, 'work')
        self.assertFalse(cat.is_default)

    def test_category_unique_constraint(self):
        """Test duplicate category names are prevented."""
        Category.objects.create(user=self.user, name='Work')
        with self.assertRaises(Exception):
            Category.objects.create(user=self.user, name='Work')

    def test_category_auto_slug(self):
        """Test slug is auto-generated from name."""
        cat = Category.objects.create(user=self.user, name='My Category')
        self.assertEqual(cat.slug, 'my-category')


class TaskModelTest(TestCase):
    """Test Task model behavior and properties."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.category = Category.objects.create(
            user=self.user,
            name='Work',
            color='#64ffda'
        )

    def test_task_creation(self):
        """Test basic task creation."""
        task = Task.objects.create(
            user=self.user,
            title='Test Task',
            description='Test description',
            status='pending',
            priority='medium',
            category=self.category,
            due_date=date.today() + timedelta(days=7)
        )
        self.assertEqual(task.title, 'Test Task')
        self.assertEqual(task.status, 'pending')
        self.assertFalse(task.is_archived)

    def test_task_is_overdue(self):
        """Test overdue detection."""
        overdue_task = Task.objects.create(
            user=self.user,
            title='Overdue',
            due_date=date.today() - timedelta(days=1)
        )
        self.assertTrue(overdue_task.is_overdue)

        completed_task = Task.objects.create(
            user=self.user,
            title='Completed',
            due_date=date.today() - timedelta(days=1),
            status='completed'
        )
        self.assertFalse(completed_task.is_overdue)

    def test_task_days_remaining(self):
        """Test days remaining calculation."""
        task = Task.objects.create(
            user=self.user,
            title='Future',
            due_date=date.today() + timedelta(days=5)
        )
        self.assertEqual(task.days_remaining, 5)

    def test_task_mark_complete(self):
        """Test mark_complete method."""
        task = Task.objects.create(user=self.user, title='To Complete')
        task.mark_complete()
        self.assertEqual(task.status, 'completed')
        self.assertIsNotNone(task.completed_at)

    def test_task_archive(self):
        """Test soft-delete via archive."""
        task = Task.objects.create(user=self.user, title='To Archive')
        task.archive()
        self.assertTrue(task.is_archived)

    def test_task_unarchive(self):
        """Test restore from archive."""
        task = Task.objects.create(user=self.user, title='To Restore', is_archived=True)
        task.unarchive()
        self.assertFalse(task.is_archived)


# =============================================================================
# FORM TESTS
# =============================================================================

class TaskFormTest(TestCase):
    """Test TaskForm validation."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_valid_task_form(self):
        """Test form with valid data."""
        data = {
            'title': 'Valid Task',
            'description': 'Description',
            'status': 'pending',
            'priority': 'medium',
            'due_date': date.today() + timedelta(days=7),
            'tags_input': 'work, urgent',
        }
        form = TaskForm(data=data, user=self.user)
        self.assertTrue(form.is_valid())

    def test_past_due_date_invalid(self):
        """Test past due date is rejected."""
        data = {
            'title': 'Invalid',
            'due_date': date.today() - timedelta(days=1),
        }
        form = TaskForm(data=data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('due_date', form.errors)

    def test_tags_parsing(self):
        """Test comma-separated tags are parsed correctly."""
        data = {
            'title': 'Tagged',
            'tags_input': '  work ,  URGENT , work, client-a  ',
        }
        form = TaskForm(data=data, user=self.user)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['tags_input'], ['work', 'urgent', 'client-a'])


class SignUpFormTest(TestCase):
    """Test user registration form."""

    def test_valid_signup(self):
        """Test valid registration."""
        data = {
            'username': 'newuser',
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        form = SignUpForm(data=data)
        self.assertTrue(form.is_valid())

    def test_duplicate_email(self):
        """Test duplicate email is rejected."""
        User.objects.create_user('existing', email='john@example.com', password='pass')
        data = {
            'username': 'newuser',
            'email': 'john@example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        form = SignUpForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)


# =============================================================================
# VIEW TESTS
# =============================================================================

class TaskViewTest(TestCase):
    """Test task views with authentication."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        self.category = Category.objects.create(user=self.user, name='Work')

    def test_task_list_view(self):
        """Test task list page loads."""
        response = self.client.get(reverse('tasks:task_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tasks/task_list.html')

    def test_task_create_view(self):
        """Test task creation."""
        data = {
            'title': 'New Task',
            'description': 'Description',
            'status': 'pending',
            'priority': 'medium',
            'category': self.category.id,
            'tags_input': 'work',
        }
        response = self.client.post(reverse('tasks:task_create'), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        self.assertTrue(Task.objects.filter(title='New Task').exists())

    def test_task_detail_view(self):
        """Test task detail page."""
        task = Task.objects.create(
            user=self.user,
            title='Detail Task',
            category=self.category
        )
        response = self.client.get(reverse('tasks:task_detail', kwargs={'pk': task.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detail Task')

    def test_task_update_view(self):
        """Test task editing."""
        task = Task.objects.create(user=self.user, title='Old Title')
        data = {
            'title': 'Updated Title',
            'description': 'Updated',
            'status': 'in_progress',
            'priority': 'high',
            'tags_input': '',
        }
        response = self.client.post(
            reverse('tasks:task_edit', kwargs={'pk': task.pk}),
            data
        )
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.title, 'Updated Title')

    def test_task_delete_view(self):
        """Test task soft-delete (archive)."""
        task = Task.objects.create(user=self.user, title='To Delete')
        response = self.client.post(reverse('tasks:task_delete', kwargs={'pk': task.pk}))
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertTrue(task.is_archived)

    def test_unauthorized_access(self):
        """Test other users cannot access tasks."""
        other_user = User.objects.create_user('other', password='pass')
        task = Task.objects.create(user=other_user, title='Private')

        response = self.client.get(reverse('tasks:task_detail', kwargs={'pk': task.pk}))
        self.assertEqual(response.status_code, 404)


# =============================================================================
# API TESTS
# =============================================================================

class TaskAPITest(APITestCase):
    """Test REST API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='apitest',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        self.category = Category.objects.create(user=self.user, name='API Cat')
        self.task = Task.objects.create(
            user=self.user,
            title='API Task',
            category=self.category
        )

    def test_list_tasks(self):
        """Test GET /api/v1/tasks/"""
        response = self.client.get('/api/v1/tasks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_create_task(self):
        """Test POST /api/v1/tasks/"""
        data = {
            'title': 'New API Task',
            'description': 'Created via API',
            'status': 'pending',
            'priority': 'high',
            'category_id': str(self.category.id),
            'due_date': (date.today() + timedelta(days=7)).isoformat(),
            'tags': ['api', 'test'],
        }
        response = self.client.post('/api/v1/tasks/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Task.objects.filter(title='New API Task').exists())

    def test_retrieve_task(self):
        """Test GET /api/v1/tasks/{id}/"""
        response = self.client.get(f'/api/v1/tasks/{self.task.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'API Task')

    def test_update_task(self):
        """Test PATCH /api/v1/tasks/{id}/"""
        data = {'title': 'Updated API Task', 'status': 'completed'}
        response = self.client.patch(f'/api/v1/tasks/{self.task.id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, 'Updated API Task')

    def test_delete_task(self):
        """Test DELETE /api/v1/tasks/{id}/ (soft delete)"""
        response = self.client.delete(f'/api/v1/tasks/{self.task.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.task.refresh_from_db()
        self.assertTrue(self.task.is_archived)

    def test_toggle_status(self):
        """Test POST /api/v1/tasks/{id}/toggle_status/"""
        data = {'status': 'completed'}
        response = self.client.post(f'/api/v1/tasks/{self.task.id}/toggle_status/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'completed')

    def test_dashboard_stats(self):
        """Test GET /api/v1/tasks/dashboard/"""
        response = self.client.get('/api/v1/tasks/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total', response.data)
        self.assertIn('pending', response.data)

    def test_unauthorized_api_access(self):
        """Test unauthenticated requests are blocked."""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/v1/tasks/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_other_user_task_access(self):
        """Test users cannot access others' tasks."""
        other_user = User.objects.create_user('other', password='pass')
        other_task = Task.objects.create(user=other_user, title='Private')
        response = self.client.get(f'/api/v1/tasks/{other_task.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
