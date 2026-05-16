"""
Smart Task Manager - URL Configuration
Clean URL patterns with logical grouping.
"""

from django.urls import path

from . import views

app_name = 'tasks'

urlpatterns = [
    # Home & Auth
    path('', views.HomeView.as_view(), name='home'),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),

    # Tasks
    path('tasks/', views.TaskListView.as_view(), name='task_list'),
    path('tasks/create/', views.TaskCreateView.as_view(), name='task_create'),
    path('tasks/<uuid:pk>/', views.TaskDetailView.as_view(), name='task_detail'),
    path('tasks/<uuid:pk>/edit/', views.TaskUpdateView.as_view(), name='task_edit'),
    path('tasks/<uuid:pk>/delete/', views.TaskDeleteView.as_view(), name='task_delete'),
    path('tasks/<uuid:pk>/toggle/', views.task_toggle_status, name='task_toggle'),
    path('tasks/<uuid:pk>/restore/', views.task_restore, name='task_restore'),

    # Attachments
    path('tasks/<uuid:task_pk>/attach/', views.attachment_upload, name='attachment_upload'),
    path('attachments/<uuid:pk>/delete/', views.attachment_delete, name='attachment_delete'),

    # Categories
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<uuid:pk>/edit/', views.CategoryUpdateView.as_view(), name='category_edit'),
    path('categories/<uuid:pk>/delete/', views.CategoryDeleteView.as_view(), name='category_delete'),
]
