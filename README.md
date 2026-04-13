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

## Deploy To Railway
1. Create a new Railway project and connect this repository.
2. Add PostgreSQL plugin (and Redis plugin if you plan to run Celery workers).
3. Set service start command to `gunicorn elibrary.wsgi --log-file -`.
4. Set build command to `pip install -r requirements.txt && python manage.py collectstatic --noinput`.
5. Run migrations once after deploy:
   - `python manage.py migrate`

### Required Environment Variables
- `DJANGO_SECRET_KEY`: strong random value.
- `DJANGO_DEBUG=0`
- `DJANGO_ALLOWED_HOSTS=.up.railway.app`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://your-app-name.up.railway.app`
- `DATABASE_URL`: provided automatically by Railway PostgreSQL plugin.

### Optional Environment Variables
- `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` for background tasks.
- S3 settings (`USE_S3=1`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, etc.) for cloud media/static storage.

### Railway Media Storage (if not using S3)
- Attach a persistent volume in Railway and mount it to `/data`.
- Set `DJANGO_MEDIA_ROOT=/data/media`.
- Set `DJANGO_SERVE_MEDIA=1` (small deployments only; for larger scale prefer S3).
- Set `DJANGO_DEBUG=0` in production.
