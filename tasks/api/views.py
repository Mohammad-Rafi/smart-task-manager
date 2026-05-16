"""
Smart Task Manager API Views
Django REST Framework ViewSets for Tasks, Categories, and Attachments
With Input Validation for Security
"""

import os
import uuid
import re
from datetime import datetime, timedelta

from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.exceptions import ValidationError as DRFValidationError
from django_filters.rest_framework import DjangoFilterBackend

from tasks.models import Task, Category, TaskAttachment, TaskActivity
from .serializers import (
    CategorySerializer,
    TaskListSerializer,
    TaskDetailSerializer,
    TaskCreateUpdateSerializer,
    TaskAttachmentSerializer,
    TaskActivitySerializer,
    DashboardStatsSerializer,
    TaskFilterSerializer,
)
from .permissions import IsOwnerOrAdmin


# =============================================================================
# INPUT VALIDATION HELPERS
# =============================================================================

def validate_string_input(value, field_name, max_length=200, allow_empty=False):
    """Validate string input - strip HTML, check length, prevent injection."""
    if not allow_empty and not value:
        raise DRFValidationError({field_name: f'{field_name} is required.'})

    if value:
        # Strip HTML tags to prevent XSS
        value = re.sub(r'<[^>]+>', '', str(value))
        # Strip potentially dangerous characters
        value = re.sub(r"[<<>'\"%;()&+]", '', value)

        if len(value) > max_length:
            raise DRFValidationError({field_name: f'{field_name} must be less than {max_length} characters.'})

    return value.strip() if value else value


def validate_choice_input(value, field_name, valid_choices):
    """Validate that value is in allowed choices."""
    if not value:
        raise DRFValidationError({field_name: f'{field_name} is required.'})

    valid_values = [choice[0] for choice in valid_choices]
    if value not in valid_values:
        raise DRFValidationError({
            field_name: f'Invalid {field_name}. Choose from: {", ".join(valid_values)}'
        })

    return value


def validate_date_input(value, field_name, allow_past=False):
    """Validate date input format and range."""
    if not value:
        return None

    try:
        if isinstance(value, str):
            parsed_date = datetime.strptime(value, '%Y-%m-%d').date()
        else:
            parsed_date = value

        if not allow_past and parsed_date < timezone.now().date():
            raise DRFValidationError({field_name: f'{field_name} must be today or in the future.'})

        return parsed_date
    except ValueError:
        raise DRFValidationError({field_name: f'Invalid {field_name} format. Use YYYY-MM-DD.'})


def validate_file_upload(file_obj, max_size_mb=10):
    """Validate uploaded file - size, type, extension."""
    if not file_obj:
        raise DRFValidationError({'file': 'No file provided.'})

    # Check file size (max 10MB)
    max_size = max_size_mb * 1024 * 1024
    if file_obj.size > max_size:
        raise DRFValidationError({'file': f'File size must be less than {max_size_mb}MB.'})

    # Check allowed extensions
    allowed_extensions = ['.pdf', '.doc', '.docx', '.txt', '.jpg', '.jpeg', '.png', '.gif']
    ext = os.path.splitext(file_obj.name)[1].lower()
    if ext not in allowed_extensions:
        raise DRFValidationError({
            'file': f'Invalid file type. Allowed: {", ".join(allowed_extensions)}'
        })

    # Check MIME type
    allowed_mimes = [
        'application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain', 'image/jpeg', 'image/png', 'image/gif'
    ]
    if hasattr(file_obj, 'content_type') and file_obj.content_type:
        if file_obj.content_type not in allowed_mimes:
            raise DRFValidationError({'file': 'Invalid file content type.'})

    return file_obj


def sanitize_tags(tags):
    """Sanitize tag input - limit count, strip special chars."""
    if not tags:
        return []

    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(',')]

    # Limit to 10 tags
    tags = tags[:10]

    # Sanitize each tag
    sanitized = []
    for tag in tags:
        if tag:
            # Remove HTML and special chars
            clean_tag = re.sub(r'<[^>]+>', '', str(tag))
            clean_tag = re.sub(r"[<<>'\"%;()&+]", '', clean_tag)
            clean_tag = clean_tag.strip()
            if clean_tag and len(clean_tag) <= 50:
                sanitized.append(clean_tag)

    return sanitized


# =============================================================================
# VIEWSETS
# =============================================================================

class CategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for managing task categories with input validation."""
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        """Return categories for the current user."""
        return Category.objects.filter(
            Q(user=self.request.user) | Q(is_default=True)
        ).distinct()

    def perform_create(self, serializer):
        """Set the user when creating a category with validated input."""
        # Validate category name
        name = self.request.data.get('name', '')
        validated_name = validate_string_input(name, 'name', max_length=100)

        # Validate color (hex format)
        color = self.request.data.get('color', '#64ffda')
        if color and not re.match(r'^#[0-9A-Fa-f]{6}$', str(color)):
            raise DRFValidationError({'color': 'Color must be in hex format (e.g., #64ffda).'})

        # Check for duplicate category name
        if Category.objects.filter(user=self.request.user, name__iexact=validated_name).exists():
            raise DRFValidationError({'name': 'A category with this name already exists.'})

        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        """Update category with validated input."""
        name = self.request.data.get('name', '')
        if name:
            validated_name = validate_string_input(name, 'name', max_length=100)
            # Check for duplicate (excluding current instance)
            if Category.objects.filter(
                user=self.request.user, 
                name__iexact=validated_name
            ).exclude(id=serializer.instance.id).exists():
                raise DRFValidationError({'name': 'A category with this name already exists.'})

        serializer.save()


class TaskViewSet(viewsets.ModelViewSet):
    """ViewSet for managing tasks with full CRUD operations and input validation."""
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'priority', 'category']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'updated_at', 'due_date', 'priority']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action in ['create', 'update', 'partial_update']:
            return TaskCreateUpdateSerializer
        elif self.action == 'retrieve':
            return TaskDetailSerializer
        return TaskListSerializer

    def get_queryset(self):
        """Return tasks for the current user with optional filtering."""
        queryset = Task.objects.filter(user=self.request.user)

        # Filter by archived status
        is_archived = self.request.query_params.get('archived', 'false').lower() == 'true'
        queryset = queryset.filter(is_archived=is_archived)

        # Filter by date range
        date_from = self.request.query_params.get('from')
        date_to = self.request.query_params.get('to')
        if date_from:
            queryset = queryset.filter(due_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(due_date__lte=date_to)

        return queryset.select_related('category').prefetch_related('attachments', 'activities')

    def perform_create(self, serializer):
        """Create task with validated input."""
        data = self.request.data

        # Validate title
        title = data.get('title', '')
        validate_string_input(title, 'title', max_length=200)

        # Validate description
        description = data.get('description', '')
        if description:
            validate_string_input(description, 'description', max_length=2000, allow_empty=True)

        # Validate status
        status_val = data.get('status', 'pending')
        validate_choice_input(status_val, 'status', Task._meta.get_field('status').choices)

        # Validate priority
        priority = data.get('priority', 'medium')
        validate_choice_input(priority, 'priority', Task._meta.get_field('priority').choices)

        # Validate due date
        due_date = data.get('due_date')
        if due_date:
            validate_date_input(due_date, 'due_date')

        # Validate category (must belong to user)
        category_id = data.get('category')
        if category_id:
            try:
                category = Category.objects.get(id=category_id, user=self.request.user)
            except Category.DoesNotExist:
                raise DRFValidationError({'category': 'Invalid category or you do not have permission to use it.'})

        # Sanitize tags
        tags = data.get('tags', [])
        if tags:
            sanitized_tags = sanitize_tags(tags)
            # Note: You may need to adjust how tags are stored in your model

        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        """Update task with validated input."""
        data = self.request.data

        # Validate title if provided
        title = data.get('title')
        if title is not None:
            validate_string_input(title, 'title', max_length=200)

        # Validate description if provided
        description = data.get('description')
        if description is not None:
            validate_string_input(description, 'description', max_length=2000, allow_empty=True)

        # Validate status if provided
        status_val = data.get('status')
        if status_val is not None:
            validate_choice_input(status_val, 'status', Task._meta.get_field('status').choices)

        # Validate priority if provided
        priority = data.get('priority')
        if priority is not None:
            validate_choice_input(priority, 'priority', Task._meta.get_field('priority').choices)

        # Validate due date if provided
        due_date = data.get('due_date')
        if due_date:
            validate_date_input(due_date, 'due_date')

        # Validate category if provided
        category_id = data.get('category')
        if category_id:
            try:
                category = Category.objects.get(id=category_id, user=self.request.user)
            except Category.DoesNotExist:
                raise DRFValidationError({'category': 'Invalid category or you do not have permission to use it.'})

        # Sanitize tags if provided
        tags = data.get('tags')
        if tags is not None:
            sanitized_tags = sanitize_tags(tags)

        task = serializer.save()
        TaskActivity.objects.create(
            task=task,
            user=self.request.user,
            action='updated',
            description='Task was updated'
        )

    @action(detail=True, methods=['post'])
    def toggle_status(self, request, pk=None):
        """Toggle task status with validation."""
        task = self.get_object()
        new_status = request.data.get('status')

        # Validate status is provided
        if not new_status:
            return Response(
                {'detail': 'Status is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate status is a valid choice
        valid_statuses = [choice[0] for choice in Task._meta.get_field('status').choices]
        if new_status not in valid_statuses:
            return Response(
                {"detail": f'Invalid status. Choose from: {", ".join(valid_statuses)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_status = task.status
        task.status = new_status
        if new_status == 'completed':
            task.completed_at = timezone.now()
        else:
            task.completed_at = None
        task.save(update_fields=['status', 'completed_at', 'updated_at'])

        TaskActivity.objects.create(
            task=task,
            user=request.user,
            action='status_changed',
            old_value={'status': old_status},
            new_value={'status': new_status},
            description=f'Status changed from {old_status} to {new_status}'
        )

        return Response({
            'id': str(task.id),
            'status': task.status,
            'status_display': task.get_status_display(),
            'completed_at': task.completed_at,
        })

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restore archived task."""
        task = self.get_object()
        if not task.is_archived:
            return Response(
                {'detail': 'Task is not archived.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        task.is_archived = False
        task.save(update_fields=['is_archived', 'updated_at'])

        TaskActivity.objects.create(
            task=task,
            user=request.user,
            action='restored',
            description='Task was restored from archive'
        )

        return Response({
            'id': str(task.id),
            'is_archived': task.is_archived,
            'message': 'Task restored successfully'
        })

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive a task."""
        task = self.get_object()
        if task.is_archived:
            return Response(
                {'detail': 'Task is already archived.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        task.is_archived = True
        task.save(update_fields=['is_archived', 'updated_at'])

        TaskActivity.objects.create(
            task=task,
            user=request.user,
            action='archived',
            description='Task was archived'
        )

        return Response({
            'id': str(task.id),
            'is_archived': task.is_archived,
            'message': 'Task archived successfully'
        })

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get task statistics for the current user."""
        user = request.user
        total_tasks = Task.objects.filter(user=user).count()
        completed_tasks = Task.objects.filter(user=user, status='completed').count()
        pending_tasks = Task.objects.filter(user=user, status='pending').count()
        in_progress_tasks = Task.objects.filter(user=user, status='in_progress').count()
        archived_tasks = Task.objects.filter(user=user, is_archived=True).count()
        overdue_tasks = Task.objects.filter(
            user=user,
            due_date__lt=timezone.now(),
            status__in=['pending', 'in_progress']
        ).count()

        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

        serializer = DashboardStatsSerializer(data={
            'total': total_tasks,
            'pending': pending_tasks,
            'in_progress': in_progress_tasks,
            'completed': completed_tasks,
            'overdue': overdue_tasks,
        })
        serializer.is_valid(raise_exception=True)

        data = serializer.data
        data['archived'] = archived_tasks
        data['completion_rate'] = round(completion_rate, 2)

        return Response(data)

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get dashboard data with recent and upcoming tasks."""
        user = request.user
        recent_tasks = Task.objects.filter(user=user).order_by('-updated_at')[:5]
        upcoming_tasks = Task.objects.filter(
            user=user,
            due_date__gte=timezone.now(),
            status__in=['pending', 'in_progress']
        ).order_by('due_date')[:5]

        return Response({
            'recent_tasks': TaskListSerializer(recent_tasks, many=True).data,
            'upcoming_tasks': TaskListSerializer(upcoming_tasks, many=True).data,
        })


class TaskAttachmentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing task attachments with file validation."""
    serializer_class = TaskAttachmentSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        """Return attachments for tasks owned by the current user."""
        return TaskAttachment.objects.filter(task__user=self.request.user)

    def perform_create(self, serializer):
        """Handle file upload with validation."""
        task_id = self.request.data.get('task')

        # Validate task_id
        if not task_id:
            raise DRFValidationError({'task': 'Task ID is required.'})

        try:
            task = get_object_or_404(Task, id=task_id, user=self.request.user)
        except Exception:
            raise DRFValidationError({'task': 'Invalid task or you do not have permission.'})

        # Validate file upload
        file_obj = self.request.FILES.get('file')
        validate_file_upload(file_obj, max_size_mb=10)

        serializer.save(
            task=task,
            file=file_obj,
        )

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download attachment file."""
        attachment = self.get_object()
        file_path = attachment.file.path

        if not os.path.exists(file_path):
            return Response(
                {'detail': 'File not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        from django.http import FileResponse
        return FileResponse(
            open(file_path, 'rb'),
            as_attachment=True,
            filename=attachment.filename
        )