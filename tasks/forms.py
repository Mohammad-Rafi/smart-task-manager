"""
Smart Task Manager - Form Classes
Custom forms with validation, widgets, and clean architecture.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Category, Task, TaskAttachment


class BootstrapFormMixin:
    """
    Mixin to add Bootstrap CSS classes to all form fields.
    Eliminates repetitive widget configuration.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.EmailInput, 
                                          forms.PasswordInput, forms.NumberInput,
                                          forms.DateInput, forms.Select)):
                field.widget.attrs.update({
                    'class': 'form-control',
                    'placeholder': field.label or field_name.replace('_', ' ').title(),
                })
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': field.label or field_name.replace('_', ' ').title(),
                })
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})


class SignUpForm(BootstrapFormMixin, UserCreationForm):
    """
    Custom user registration form with email validation.
    Prevents duplicate email registration.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email',
            'autocomplete': 'email',
        }),
        help_text="We'll never share your email with anyone."
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name',
            'autocomplete': 'given-name',
        }),
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name',
            'autocomplete': 'family-name',
        }),
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

    def clean_email(self):
        """Validate email uniqueness."""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('A user with this email already exists.')
        return email

    def save(self, commit=True):
        """Save user with proper name fields."""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    """
    Custom login form with enhanced styling.
    """
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username or email',
            'autocomplete': 'username',
            'autofocus': True,
        }),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password',
            'autocomplete': 'current-password',
        }),
    )


class CategoryForm(BootstrapFormMixin, forms.ModelForm):
    """
    Form for creating and editing categories.
    Validates unique category names per user.
    """
    class Meta:
        model = Category
        fields = ['name', 'color']
        widgets = {
            'color': forms.TextInput(attrs={
                'type': 'color',
                'class': 'form-control form-control-color',
            }),
        }

    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_name(self):
        """Ensure unique category name for this user."""
        name = self.cleaned_data.get('name')
        if self.user:
            qs = Category.objects.filter(user=self.user, name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError('You already have a category with this name.')
        return name


class TaskForm(BootstrapFormMixin, forms.ModelForm):
    """
    Comprehensive task creation/editing form.
    Includes smart defaults and validation.
    """
    tags_input = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'work, urgent, client-a (comma separated)',
        }),
        help_text="Enter tags separated by commas",
    )

    class Meta:
        model = Task
        fields = ['title', 'description', 'status', 'priority', 'category', 'due_date', 'tags_input']
        widgets = {
            'due_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'min': timezone.now().date().isoformat(),
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe the task in detail...',
            }),
        }

    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        # Filter categories to user's own only
        if user:
            self.fields['category'].queryset = Category.objects.filter(user=user)
            self.fields['category'].required = False

        # Pre-populate tags if editing
        if self.instance.pk and self.instance.tags:
            self.fields['tags_input'].initial = ', '.join(self.instance.tags)

    def clean_due_date(self):
        """Validate due date is not in the past."""
        due_date = self.cleaned_data.get('due_date')
        if due_date and due_date < timezone.now().date():
            if self.instance.pk and self.instance.due_date == due_date:
                return due_date  # Allow existing past dates when editing
            raise ValidationError('Due date cannot be in the past.')
        return due_date

    def clean_tags_input(self):
        """Parse comma-separated tags into clean list."""
        tags_raw = self.cleaned_data.get('tags_input', '')
        if not tags_raw:
            return []
        tags = [tag.strip().lower() for tag in tags_raw.split(',') if tag.strip()]
        # Remove duplicates while preserving order
        seen = set()
        unique_tags = []
        for tag in tags:
            if tag not in seen and len(tag) <= 30:
                seen.add(tag)
                unique_tags.append(tag)
        return unique_tags[:10]  # Max 10 tags

    def save(self, commit=True):
        """Save task with parsed tags."""
        task = super().save(commit=False)
        task.tags = self.cleaned_data.get('tags_input', [])
        if self.user:
            task.user = self.user
        if commit:
            task.save()
        return task


class TaskFilterForm(forms.Form):
    """
    Filter form for task list view.
    No ModelForm — pure filtering logic.
    """
    STATUS_CHOICES = [('', 'All Statuses')] + Task._meta.get_field('status').choices
    PRIORITY_CHOICES = [('', 'All Priorities')] + Task._meta.get_field('priority').choices

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    priority = forms.ChoiceField(
        choices=PRIORITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.none(),
        required=False,
        empty_label='All Categories',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search tasks...',
        }),
    )
    due_before = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
        }),
    )
    show_archived = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        initial=False,
    )

    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['category'].queryset = Category.objects.filter(user=user)


class TaskAttachmentForm(BootstrapFormMixin, forms.ModelForm):
    """
    Form for uploading file attachments to tasks.
    Validates file size and type.
    """
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_TYPES = [
        'image/jpeg', 'image/png', 'image/gif',
        'application/pdf', 'text/plain',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ]

    class Meta:
        model = TaskAttachment
        fields = ['file']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.jpg,.jpeg,.png,.gif,.pdf,.txt,.doc,.docx',
            }),
        }

    def clean_file(self):
        """Validate file size and type."""
        file = self.cleaned_data.get('file')
        if not file:
            return file

        if file.size > self.MAX_FILE_SIZE:
            raise ValidationError(f'File size must not exceed 10MB. Current: {file.size / 1024 / 1024:.1f}MB')

        if file.content_type not in self.ALLOWED_TYPES:
            raise ValidationError(f'File type "{file.content_type}" not allowed. Allowed: images, PDF, DOC, TXT.')

        return file
