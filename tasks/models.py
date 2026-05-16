"""
Smart Task Manager - Data Models
Optimized with database indexes, validators, and clean relationships.
"""

import uuid
from datetime import date

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinLengthValidator, MaxLengthValidator
from django.core.exceptions import ValidationError
from django.utils import timezone

from smart_task_manager.settings import (
    TASK_STATUS_CHOICES,
    TASK_PRIORITY_CHOICES,
    TASK_CATEGORY_CHOICES,
)


class TimestampMixin(models.Model):
    """
    Abstract base model providing created_at and updated_at timestamps.
    All models inherit from this for consistent audit trails.
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']


class Category(TimestampMixin):
    """
    Task category model with user-scoped categories.
    Prevents category name duplication per user.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=50,
        validators=[MinLengthValidator(2), MaxLengthValidator(50)],
        help_text="Category name (2-50 characters)"
    )
    slug = models.SlugField(max_length=60, blank=True)
    color = models.CharField(
        max_length=7,
        default='#64ffda',
        help_text="Hex color code for category badge"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='categories',
        db_index=True,
    )
    is_default = models.BooleanField(default=False, help_text="System default category")

    class Meta:
        db_table = 'task_categories'
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'name'],
                name='unique_category_per_user',
                violation_error_message="You already have a category with this name."
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'is_default'], name='idx_user_default_cat'),
        ]

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    def save(self, *args, **kwargs):
        """Auto-generate slug from name."""
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def clean(self):
        """Validate color hex format."""
        if self.color and not self.color.startswith('#'):
            raise ValidationError({'color': 'Color must be a valid hex code (e.g., #64ffda)'})


class Task(TimestampMixin):
    """
    Core Task model with comprehensive status tracking.
    Optimized with strategic database indexes for fast queries.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(
        max_length=200,
        validators=[MinLengthValidator(3), MaxLengthValidator(200)],
        help_text="Task title (3-200 characters)"
    )
    description = models.TextField(
        blank=True,
        max_length=5000,
        help_text="Detailed description of the task"
    )
    status = models.CharField(
        max_length=20,
        choices=TASK_STATUS_CHOICES,
        default='pending',
        db_index=True,
    )
    priority = models.CharField(
        max_length=10,
        choices=TASK_PRIORITY_CHOICES,
        default='medium',
        db_index=True,
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks',
        db_index=True,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tasks',
        db_index=True,
    )
    due_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Deadline for task completion"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when task was marked complete"
    )
    is_archived = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Soft-delete flag for archived tasks"
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Array of string tags for flexible filtering"
    )

    class Meta:
        db_table = 'tasks'
        verbose_name = 'Task'
        verbose_name_plural = 'Tasks'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status', 'is_archived'], name='idx_user_status_arch'),
            models.Index(fields=['user', 'priority', 'due_date'], name='idx_user_priority_due'),
            models.Index(fields=['due_date', 'status'], name='idx_due_status'),
            models.Index(fields=['user', 'category'], name='idx_user_category'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(due_date__gte=date(2020, 1, 1)),
                name='valid_due_date',
            ),
        ]

    def __str__(self):
        return f"[{self.get_status_display()}] {self.title[:50]}"

    @property
    def is_overdue(self):
        """Check if task is past due date and not completed."""
        if self.due_date and self.status != 'completed':
            return self.due_date < date.today()
        return False

    @property
    def days_remaining(self):
        """Calculate days until deadline."""
        if self.due_date and self.status != 'completed':
            delta = self.due_date - date.today()
            return delta.days
        return None

    def mark_complete(self):
        """Mark task as completed with timestamp."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])

    def mark_in_progress(self):
        """Mark task as in progress."""
        self.status = 'in_progress'
        self.save(update_fields=['status', 'updated_at'])

    def archive(self):
        """Soft-delete by archiving."""
        self.is_archived = True
        self.save(update_fields=['is_archived', 'updated_at'])

    def unarchive(self):
        """Restore archived task."""
        self.is_archived = False
        self.save(update_fields=['is_archived', 'updated_at'])

    def clean(self):
        """Cross-field validation."""
        if self.due_date and self.due_date < date(2020, 1, 1):
            raise ValidationError({'due_date': 'Due date cannot be before 2020.'})
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()


class TaskAttachment(TimestampMixin):
    """
    File attachments for tasks with size validation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='attachments',
        db_index=True,
    )
    file = models.FileField(
        upload_to='task_attachments/%Y/%m/',
        help_text="Max file size: 10MB"
    )
    filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="Size in bytes")
    mime_type = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = 'task_attachments'
        verbose_name = 'Task Attachment'
        verbose_name_plural = 'Task Attachments'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.filename} ({self.task.title[:30]})"

    def clean(self):
        """Validate file size (10MB limit)."""
        max_size = 10 * 1024 * 1024  # 10MB
        if self.file and self.file.size > max_size:
            raise ValidationError({'file': 'File size must not exceed 10MB.'})


class TaskActivity(TimestampMixin):
    """
    Audit log for task changes — tracks who did what and when.
    Essential for collaboration and debugging.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='activities',
        db_index=True,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='task_activities',
    )
    action = models.CharField(max_length=50, db_index=True)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'task_activities'
        verbose_name = 'Task Activity'
        verbose_name_plural = 'Task Activities'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task', 'created_at'], name='idx_task_activity_time'),
        ]

    def __str__(self):
        return f"{self.action} on {self.task.title[:30]} by {self.user.username if self.user else 'system'}"
