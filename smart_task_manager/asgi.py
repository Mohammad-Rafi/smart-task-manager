"""
ASGI config for Smart Task Manager project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_task_manager.settings')

application = get_asgi_application()
