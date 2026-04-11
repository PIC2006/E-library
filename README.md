# E-Library Thesis Repository System

Scalable Django + DRF thesis repository with role-based access, PDF uploads, approval workflow, search, bookmarking, analytics, and Celery task hooks.

## Stack
- Django + Django REST Framework
- PostgreSQL-ready settings with SQLite fallback
- AWS S3-compatible storage via django-storages
- Celery + Redis
- Tailwind CSS templates

## Key Apps
- `accounts` for authentication and role management
- `theses` for thesis metadata, approval, downloads, bookmarks, analytics
- `search` for basic and advanced search

## Run
1. Create and activate a Python environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Set `DJANGO_SECRET_KEY` and optional PostgreSQL, Redis, and S3 environment variables.
4. Run migrations and start the server:
   - `python manage.py makemigrations`
   - `python manage.py migrate`
   - `python manage.py runserver`
5. Bootstrap demo data and a superuser if needed:
   - `python manage.py bootstrap_elibrary --create-superuser --seed --seed-users`

## Notes
- Advanced search uses PostgreSQL full-text search when available and falls back to ORM search.
- PDF previews are generated asynchronously as page images and exposed in the detail page and API.
- Celery task `process_thesis_upload` extracts PDF text for search indexing and triggers preview generation.
