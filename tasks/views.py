"""
Smart Task Manager - View Layer
Class-based views with LoginRequiredMixin, pagination, and clean separation.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
)
from django.views.generic.edit import FormView
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q, Count
from django.utils import timezone
from django.core.paginator import Paginator

from .models import Category, Task, TaskAttachment, TaskActivity
from .forms import (
    SignUpForm, LoginForm, CategoryForm, TaskForm,
    TaskFilterForm, TaskAttachmentForm
)


# =============================================================================
# AUTHENTICATION VIEWS
# =============================================================================

class HomeView(TemplateView):
    """Landing page for unauthenticated users."""
    template_name = 'tasks/home.html'

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('tasks:task_list')
        return super().get(request, *args, **kwargs)


class SignUpView(FormView):
    """User registration with automatic login."""
    template_name = 'tasks/auth/signup.html'
    form_class = SignUpForm
    success_url = reverse_lazy('tasks:task_list')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, f'Welcome, {user.first_name}! Your account has been created.')

        # Create default categories for new user
        default_categories = [
            {'name': 'Work', 'color': '#64ffda'},
            {'name': 'Personal', 'color': '#ffd166'},
            {'name': 'Study', 'color': '#118ab2'},
        ]
        for cat in default_categories:
            Category.objects.get_or_create(
                user=user,
                name=cat['name'],
                defaults={'color': cat['color'], 'is_default': True}
            )

        return super().form_valid(form)


class LoginView(FormView):
    """Custom login view with form styling."""
    template_name = 'tasks/auth/login.html'
    form_class = LoginForm
    success_url = reverse_lazy('tasks:task_list')

    def form_valid(self, form):
        login(self.request, form.get_user())
        messages.success(self.request, 'Welcome back!')
        return super().form_valid(form)

    def get_success_url(self):
        """Redirect to next page if specified, otherwise task list."""
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        return self.success_url


@login_required
def logout_view(request):
    """Logout with confirmation message."""
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('tasks:home')


# =============================================================================
# DASHBOARD VIEW
# =============================================================================

class DashboardView(LoginRequiredMixin, TemplateView):
    """
    User dashboard with task statistics and quick overview.
    LoginRequiredMixin ensures only authenticated users access this.
    """
    template_name = 'tasks/dashboard.html'
    login_url = reverse_lazy('tasks:login')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Task statistics
        base_qs = Task.objects.filter(user=user, is_archived=False)
        context['stats'] = {
            'total': base_qs.count(),
            'pending': base_qs.filter(status='pending').count(),
            'in_progress': base_qs.filter(status='in_progress').count(),
            'completed': base_qs.filter(status='completed').count(),
            'overdue': base_qs.filter(due_date__lt=timezone.now().date()).exclude(status='completed').count(),
        }

        # Priority breakdown
        context['priority_stats'] = dict(
            base_qs.values('priority').annotate(count=Count('priority')).values_list('priority', 'count')
        )

        # Recent tasks
        context['recent_tasks'] = base_qs.select_related('category').order_by('-updated_at')[:5]

        # Upcoming deadlines (next 7 days)
        upcoming = base_qs.filter(
            due_date__gte=timezone.now().date(),
            due_date__lte=timezone.now().date() + timezone.timedelta(days=7),
        ).exclude(status='completed').order_by('due_date')
        context['upcoming_tasks'] = upcoming[:5]

        # Categories with task counts
        context['categories'] = Category.objects.filter(user=user).annotate(
            task_count=Count('tasks', filter=Q(tasks__is_archived=False))
        ).order_by('-task_count')

        return context


# =============================================================================
# TASK VIEWS
# =============================================================================

class TaskListView(LoginRequiredMixin, ListView):
    """
    Paginated task list with filtering and search.
    Optimized with select_related for N+1 prevention.
    """
    model = Task
    template_name = 'tasks/task_list.html'
    context_object_name = 'tasks'
    paginate_by = 12
    login_url = reverse_lazy('tasks:login')

    def get_queryset(self):
        """Apply filters from GET parameters."""
        user = self.request.user
        queryset = Task.objects.filter(user=user).select_related('category')

        # Filter form processing
        self.filter_form = TaskFilterForm(user=user, data=self.request.GET)
        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data

            if data.get('status'):
                queryset = queryset.filter(status=data['status'])
            if data.get('priority'):
                queryset = queryset.filter(priority=data['priority'])
            if data.get('category'):
                queryset = queryset.filter(category=data['category'])
            if data.get('search'):
                search = data['search']
                queryset = queryset.filter(
                    Q(title__icontains=search) |
                    Q(description__icontains=search) |
                    Q(tags__icontains=search)
                )
            if data.get('due_before'):
                queryset = queryset.filter(due_date__lte=data['due_before'])
            if not data.get('show_archived'):
                queryset = queryset.filter(is_archived=False)

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        context['total_count'] = self.get_queryset().count()

        # Status counts for sidebar
        user = self.request.user
        base = Task.objects.filter(user=user, is_archived=False)
        context['status_counts'] = {
            'all': base.count(),
            'pending': base.filter(status='pending').count(),
            'in_progress': base.filter(status='in_progress').count(),
            'completed': base.filter(status='completed').count(),
        }
        return context


class TaskDetailView(LoginRequiredMixin, DetailView):
    """
    Task detail with attachments and activity log.
    prefetch_related prevents N+1 on attachments.
    """
    model = Task
    template_name = 'tasks/task_detail.html'
    context_object_name = 'task'
    login_url = reverse_lazy('tasks:login')
    slug_url_kwarg = 'pk'

    def get_queryset(self):
        return Task.objects.filter(user=self.request.user).prefetch_related('attachments', 'activities')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['attachment_form'] = TaskAttachmentForm()
        context['activities'] = self.object.activities.select_related('user').order_by('-created_at')[:10]
        return context


class TaskCreateView(LoginRequiredMixin, CreateView):
    """Create new task with current user auto-assigned."""
    model = Task
    form_class = TaskForm
    template_name = 'tasks/task_form.html'
    success_url = reverse_lazy('tasks:task_list')
    login_url = reverse_lazy('tasks:login')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)

        # Log activity
        TaskActivity.objects.create(
            task=self.object,
            user=self.request.user,
            action='created',
            new_value={'title': self.object.title, 'status': self.object.status},
            description=f'Task "{self.object.title}" created'
        )

        messages.success(self.request, 'Task created successfully!')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'Create'
        return context


class TaskUpdateView(LoginRequiredMixin, UpdateView):
    """Edit existing task with activity logging."""
    model = Task
    form_class = TaskForm
    template_name = 'tasks/task_form.html'
    login_url = reverse_lazy('tasks:login')

    def get_queryset(self):
        return Task.objects.filter(user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        # Capture old values before save
        old_values = {
            'title': self.object.title,
            'status': self.object.status,
            'priority': self.object.priority,
        }

        response = super().form_valid(form)

        # Log activity
        new_values = {
            'title': self.object.title,
            'status': self.object.status,
            'priority': self.object.priority,
        }
        TaskActivity.objects.create(
            task=self.object,
            user=self.request.user,
            action='updated',
            old_value=old_values,
            new_value=new_values,
            description=f'Task "{self.object.title}" updated'
        )

        messages.success(self.request, 'Task updated successfully!')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'Edit'
        return context

    def get_success_url(self):
        return reverse('tasks:task_detail', kwargs={'pk': self.object.pk})


class TaskDeleteView(LoginRequiredMixin, DeleteView):
    """Soft-delete task by archiving instead of permanent deletion."""
    model = Task
    template_name = 'tasks/task_confirm_delete.html'
    success_url = reverse_lazy('tasks:task_list')
    login_url = reverse_lazy('tasks:login')

    def get_queryset(self):
        return Task.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()

        # Soft delete — archive instead of delete
        self.object.archive()

        TaskActivity.objects.create(
            task=self.object,
            user=request.user,
            action='archived',
            description=f'Task "{self.object.title}" archived'
        )

        messages.info(request, 'Task archived. You can restore it from the archive.')
        return redirect(self.get_success_url())


# =============================================================================
# TASK ACTIONS (AJAX-Friendly)
# =============================================================================

@login_required
def task_toggle_status(request, pk):
    """
    Toggle task status via POST request.
    Returns JSON for AJAX, redirects for normal requests.
    """
    task = get_object_or_404(Task, pk=pk, user=request.user)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        old_status = task.status

        if new_status in dict(Task._meta.get_field('status').choices):
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

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'status': new_status,
                    'status_display': task.get_status_display(),
                })

            messages.success(request, f'Task marked as {task.get_status_display()}.')

    return redirect('tasks:task_list')


@login_required
def task_restore(request, pk):
    """Restore archived task."""
    task = get_object_or_404(Task, pk=pk, user=request.user, is_archived=True)
    task.unarchive()

    TaskActivity.objects.create(
        task=task,
        user=request.user,
        action='restored',
        description=f'Task "{task.title}" restored from archive'
    )

    messages.success(request, 'Task restored successfully!')
    return redirect('tasks:task_list')


# =============================================================================
# CATEGORY VIEWS
# =============================================================================

class CategoryListView(LoginRequiredMixin, ListView):
    """List user's categories with task counts."""
    model = Category
    template_name = 'tasks/category_list.html'
    context_object_name = 'categories'
    login_url = reverse_lazy('tasks:login')

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user).annotate(
            task_count=Count('tasks', filter=Q(tasks__is_archived=False))
        ).order_by('-is_default', 'name')


class CategoryCreateView(LoginRequiredMixin, CreateView):
    """Create new category."""
    model = Category
    form_class = CategoryForm
    template_name = 'tasks/category_form.html'
    success_url = reverse_lazy('tasks:category_list')
    login_url = reverse_lazy('tasks:login')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'Category created successfully!')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'Create'
        return context


class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    """Edit category."""
    model = Category
    form_class = CategoryForm
    template_name = 'tasks/category_form.html'
    success_url = reverse_lazy('tasks:category_list')
    login_url = reverse_lazy('tasks:login')

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'Edit'
        return context


class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    """Delete category (tasks become uncategorized)."""
    model = Category
    template_name = 'tasks/category_confirm_delete.html'
    success_url = reverse_lazy('tasks:category_list')
    login_url = reverse_lazy('tasks:login')

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user, is_default=False)

    def delete(self, request, *args, **kwargs):
        category = self.get_object()

        # Prevent deletion of default categories
        if category.is_default:
            messages.error(request, 'Default categories cannot be deleted.')
            return redirect('tasks:category_list')

        # Reassign tasks to null (uncategorized)
        Task.objects.filter(category=category).update(category=None)

        messages.success(request, f'Category "{category.name}" deleted. Tasks are now uncategorized.')
        return super().delete(request, *args, **kwargs)


# =============================================================================
# ATTACHMENT VIEWS
# =============================================================================

@login_required
def attachment_upload(request, task_pk):
    """Upload file attachment to a task."""
    task = get_object_or_404(Task, pk=task_pk, user=request.user)

    if request.method == 'POST':
        form = TaskAttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            attachment = form.save(commit=False)
            attachment.task = task
            attachment.filename = request.FILES['file'].name
            attachment.file_size = request.FILES['file'].size
            attachment.mime_type = request.FILES['file'].content_type
            attachment.save()

            TaskActivity.objects.create(
                task=task,
                user=request.user,
                action='attachment_added',
                description=f'Attachment "{attachment.filename}" added'
            )

            messages.success(request, 'File uploaded successfully!')
            return redirect('tasks:task_detail', pk=task_pk)
        else:
            messages.error(request, 'Failed to upload file. Please check the file type and size.')
            return redirect('tasks:task_detail', pk=task_pk)

    return redirect('tasks:task_detail', pk=task_pk)


@login_required
def attachment_delete(request, pk):
    """Delete file attachment."""
    attachment = get_object_or_404(TaskAttachment, pk=pk, task__user=request.user)
    task_pk = attachment.task.pk
    attachment.delete()

    messages.info(request, 'Attachment deleted.')
    return redirect('tasks:task_detail', pk=task_pk)