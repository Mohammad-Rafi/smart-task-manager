"""
Smart Task Manager - App Configuration
"""

from django.apps import AppConfig


class TasksConfig(AppConfig):
    """Task application configuration with ready signal."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tasks'
    verbose_name = 'Task Manager'

    def ready(self):
        """Import signals when app is ready."""
        pass  # Signals can be added here later
