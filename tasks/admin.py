"""
Smart Task Manager - Admin Configuration
Custom admin interfaces with search, filters, and inline editing.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from .models import Category, Task, TaskAttachment, TaskActivity


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin interface for task categories."""
    list_display = ['name', 'user', 'color_badge', 'task_count', 'is_default', 'created_at']
    list_filter = ['is_default', 'created_at']
    search_fields = ['name', 'user__username', 'user__email']
    readonly_fields = ['slug', 'created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'color', 'user', 'is_default')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def color_badge(self, obj):
        """Display color as a visual badge."""
        return format_html(
            '<span style="background:{}; padding:4px 12px; border-radius:4px; color:#fff; font-size:12px;">{}</span>',
            obj.color,
            obj.color
        )
    color_badge.short_description = 'Color'

    def task_count(self, obj):
        """Count of tasks in this category."""
        return obj.tasks.filter(is_archived=False).count()
    task_count.short_description = 'Tasks'


class TaskAttachmentInline(admin.TabularInline):
    """Inline attachment editing within task admin."""
    model = TaskAttachment
    extra = 0
    readonly_fields = ['file_size', 'mime_type', 'created_at']
    fields = ['file', 'filename', 'file_size', 'mime_type']


class TaskActivityInline(admin.TabularInline):
    """Inline activity log within task admin."""
    model = TaskActivity
    extra = 0
    readonly_fields = ['user', 'action', 'old_value', 'new_value', 'description', 'created_at']
    fields = ['action', 'user', 'description', 'created_at']
    can_delete = False
    max_num = 5


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """
    Comprehensive task admin with status indicators,
    priority badges, and quick actions.
    """
    list_display = [
        'title_short', 'user', 'status_badge', 'priority_badge',
        'category', 'due_date', 'overdue_indicator', 'is_archived', 'created_at'
    ]
    list_filter = [
        'status', 'priority', 'is_archived', 'category', 'due_date', 'created_at'
    ]
    search_fields = ['title', 'description', 'user__username', 'user__email', 'tags']
    readonly_fields = ['created_at', 'updated_at', 'completed_at', 'is_overdue']
    ordering = ['-created_at']
    inlines = [TaskAttachmentInline, TaskActivityInline]

    fieldsets = (
        ('Task Details', {
            'fields': ('title', 'description', 'user')
        }),
        ('Classification', {
            'fields': ('status', 'priority', 'category', 'tags')
        }),
        ('Scheduling', {
            'fields': ('due_date', 'completed_at')
        }),
        ('State', {
            'fields': ('is_archived', 'is_overdue')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['mark_completed', 'mark_in_progress', 'archive_tasks', 'unarchive_tasks']

    def title_short(self, obj):
        """Truncated title for list display."""
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
    title_short.short_description = 'Title'

    def status_badge(self, obj):
        """Color-coded status badge."""
        colors = {
            'pending': '#ffd166',
            'in_progress': '#118ab2',
            'completed': '#06d6a0',
            'cancelled': '#ef476f',
        }
        color = colors.get(obj.status, '#888')
        return format_html(
            '<span style="background:{}; color:#fff; padding:3px 10px; border-radius:12px; font-size:11px; font-weight:600;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def priority_badge(self, obj):
        """Color-coded priority badge."""
        colors = {
            'low': '#06d6a0',
            'medium': '#ffd166',
            'high': '#f78c6c',
            'urgent': '#ef476f',
        }
        color = colors.get(obj.priority, '#888')
        return format_html(
            '<span style="background:{}; color:#fff; padding:3px 10px; border-radius:12px; font-size:11px; font-weight:600;">{}</span>',
            color,
            obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'

    def overdue_indicator(self, obj):
        """Show overdue warning."""
        if obj.is_overdue:
            return format_html(
                '<span style="color:#ef476f; font-weight:bold;">⚠ Overdue</span>'
            )
        elif obj.days_remaining is not None and obj.days_remaining <= 2 and obj.status != 'completed':
            return format_html(
                '<span style="color:#ffd166;">⏰ {}d left</span>',
                obj.days_remaining
            )
        return format_html('<span style="color:#06d6a0;">✓ On Track</span>')
    overdue_indicator.short_description = 'Health'

    @admin.action(description='Mark selected tasks as completed')
    def mark_completed(self, request, queryset):
        """Bulk action to complete tasks."""
        count = queryset.update(status='completed', completed_at=timezone.now())
        self.message_user(request, f'{count} task(s) marked as completed.')

    @admin.action(description='Mark selected tasks as in progress')
    def mark_in_progress(self, request, queryset):
        """Bulk action to start tasks."""
        count = queryset.update(status='in_progress')
        self.message_user(request, f'{count} task(s) marked as in progress.')

    @admin.action(description='Archive selected tasks')
    def archive_tasks(self, request, queryset):
        """Bulk action to archive tasks."""
        count = queryset.update(is_archived=True)
        self.message_user(request, f'{count} task(s) archived.')

    @admin.action(description='Unarchive selected tasks')
    def unarchive_tasks(self, request, queryset):
        """Bulk action to restore tasks."""
        count = queryset.update(is_archived=False)
        self.message_user(request, f'{count} task(s) restored.')


@admin.register(TaskAttachment)
class TaskAttachmentAdmin(admin.ModelAdmin):
    """Admin for task file attachments."""
    list_display = ['filename', 'task_title', 'file_size_display', 'mime_type', 'created_at']
    list_filter = ['mime_type', 'created_at']
    search_fields = ['filename', 'task__title']
    readonly_fields = ['file_size', 'mime_type', 'created_at']

    def task_title(self, obj):
        return obj.task.title[:40]
    task_title.short_description = 'Task'

    def file_size_display(self, obj):
        """Human-readable file size."""
        size = obj.file_size
        for unit in ['B', 'KB', 'MB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} GB"
    file_size_display.short_description = 'Size'


@admin.register(TaskActivity)
class TaskActivityAdmin(admin.ModelAdmin):
    """Read-only audit log admin."""
    list_display = ['action', 'task_title', 'user', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['task__title', 'user__username', 'description']
    readonly_fields = ['task', 'user', 'action', 'old_value', 'new_value', 'description', 'created_at']
    can_delete = False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def task_title(self, obj):
        return obj.task.title[:40]
    task_title.short_description = 'Task'
