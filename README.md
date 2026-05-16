# Smart Task Manager

A production-grade Django task management application with JWT authentication, REST API, and responsive UI.

## Features

- **User Authentication** - Sign up, login, logout with Django auth
- **JWT Token Authentication** - Secure API access with refresh tokens
- **Task CRUD** - Create, read, update, delete (soft-delete/archive) tasks
- **Categories** - Custom color-coded categories per user
- **Status Tracking** - Pending, In Progress, Completed, Cancelled
- **Priority Levels** - Low, Medium, High, Urgent
- **Deadline Management** - Due dates with overdue detection
- **File Attachments** - Upload files up to 10MB per task
- **Activity Log** - Complete audit trail of all task changes
- **REST API** - Full CRUD API with filtering, pagination, search
- **Responsive UI** - Dark theme with Bootstrap 5
- **Admin Dashboard** - Custom admin with color badges and bulk actions

## Tech Stack

- Django 4.2
- Django REST Framework
- PostgreSQL (production) / SQLite (development)
- JWT Authentication (SimpleJWT)
- Bootstrap 5 + Bootstrap Icons
- Custom CSS with CSS variables

## Project Structure

```
smart_task_manager/
├── smart_task_manager/      # Project config
│   ├── settings.py           # Production-grade settings
│   ├── urls.py               # Root URL router
│   ├── wsgi.py               # WSGI entry
│   └── asgi.py               # ASGI entry
├── tasks/                     # Main application
│   ├── models.py               # 4 models with indexes & constraints
│   ├── views.py                # 15+ class-based views
│   ├── forms.py                # 6 forms with validation
│   ├── urls.py                 # App URL patterns
│   ├── admin.py                # Custom admin interfaces
│   ├── tests.py                # 40+ unit tests
│   ├── api/
│   │   ├── serializers.py      # DRF serializers
│   │   ├── views.py            # API ViewSets
│   │   ├── urls.py             # API router
│   │   └── permissions.py      # Custom permissions
│   ├── templates/tasks/        # 12 HTML templates
│   ├── static/tasks/           # CSS & JS
│   └── templatetags/           # Custom template filters
├── manage.py
├── requirements.txt
└── .env.example
```

## Quick Start

### 1. Clone & Setup

```bash
cd smart_task_manager
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 3. Database

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 4. Run

```bash
python manage.py runserver
```

Visit: http://127.0.0.1:8000/

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/auth/token/ | Obtain JWT token |
| POST | /api/v1/auth/token/refresh/ | Refresh token |
| GET | /api/v1/tasks/ | List tasks |
| POST | /api/v1/tasks/ | Create task |
| GET | /api/v1/tasks/{id}/ | Task detail |
| PATCH | /api/v1/tasks/{id}/ | Update task |
| DELETE | /api/v1/tasks/{id}/ | Archive task |
| POST | /api/v1/tasks/{id}/toggle_status/ | Change status |
| GET | /api/v1/tasks/dashboard/ | Dashboard stats |
| GET | /api/v1/categories/ | List categories |

## Running Tests

```bash
python manage.py test tasks
```

## Security Features

- CSRF protection on all forms
- JWT token rotation & blacklisting
- Rate limiting (100/hour anonymous, 1000/hour authenticated)
- File type & size validation
- XSS protection (X-Frame-Options, CSP headers)
- SQL injection protection via ORM
- User-scoped data (users cannot access others' tasks)

## Database Indexes

- `idx_user_status_arch` - Fast task filtering by user + status
- `idx_user_priority_due` - Priority + deadline queries
- `idx_due_status` - Overdue detection
- `idx_user_category` - Category-based filtering
- `idx_task_activity_time` - Activity log pagination

---

Built by Mohammad Rafi | Python Full-Stack Developer
