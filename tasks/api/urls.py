"""
Smart Task Manager API - URL Router
DRF router configuration for all API endpoints.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from .views import CategoryViewSet, TaskViewSet, TaskAttachmentViewSet

# Create router and register viewsets
router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='api-category')
router.register(r'tasks', TaskViewSet, basename='api-task')
router.register(r'attachments', TaskAttachmentViewSet, basename='api-attachment')

urlpatterns = [
    # JWT Authentication
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # API Routes
    path('', include(router.urls)),
]
