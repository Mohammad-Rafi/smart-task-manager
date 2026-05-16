"""
Smart Task Manager - Custom Template Tags & Filters
Reusable template utilities for consistent UI rendering.
"""

from django import template
from django.utils import timezone
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def status_badge_color(status):
    """Return color hex for status badge."""
    colors = {
        'pending': '#ffd166',
        'in_progress': '#118ab2',
        'completed': '#06d6a0',
        'cancelled': '#ef476f',
    }
    return colors.get(status, '#888')


@register.filter
def priority_badge_color(priority):
    """Return color hex for priority badge."""
    colors = {
        'low': '#06d6a0',
        'medium': '#ffd166',
        'high': '#f78c6c',
        'urgent': '#ef476f',
    }
    return colors.get(priority, '#888')


@register.filter
def time_ago(value):
    """Human-readable time difference."""
    if not value:
        return ''

    now = timezone.now()
    diff = now - value

    if diff.days > 365:
        years = diff.days // 365
        return f'{years} year{"s" if years > 1 else ""} ago'
    elif diff.days > 30:
        months = diff.days // 30
        return f'{months} month{"s" if months > 1 else ""} ago'
    elif diff.days > 0:
        return f'{diff.days} day{"s" if diff.days > 1 else ""} ago'
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f'{hours} hour{"s" if hours > 1 else ""} ago'
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f'{minutes} minute{"s" if minutes > 1 else ""} ago'
    else:
        return 'Just now'


@register.filter
def file_size_human(size_bytes):
    """Convert bytes to human-readable size."""
    if not size_bytes:
        return '0 B'

    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f'{size_bytes:.1f} {unit}'
        size_bytes /= 1024
    return f'{size_bytes:.1f} TB'


@register.filter
def truncate_chars(value, max_length=50):
    """Truncate string with ellipsis."""
    if not value:
        return ''
    if len(value) > max_length:
        return value[:max_length - 3] + '...'
    return value


@register.filter
def add_class(field, css_class):
    """Add CSS class to form field widget."""
    return field.as_widget(attrs={"class": css_class})


@register.simple_tag
def active_nav(request, url_name):
    """Return 'active' class if current URL matches."""
    from django.urls import resolve
    try:
        if resolve(request.path_info).url_name == url_name:
            return 'active'
    except:
        pass
    return ''
