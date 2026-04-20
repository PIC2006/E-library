from pathlib import Path
import os

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

USE_CLOUDINARY = os.getenv("USE_CLOUDINARY", "0") == "1"
USE_S3 = os.getenv("USE_S3", "0") == "1"

if USE_CLOUDINARY and USE_S3:
    raise ImproperlyConfigured("Enable only one media backend: set either USE_CLOUDINARY=1 or USE_S3=1, not both.")

_cloudinary_url = os.getenv("CLOUDINARY_URL", "").strip()
_cloudinary_cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
_cloudinary_api_key = os.getenv("CLOUDINARY_API_KEY", "").strip()
_cloudinary_api_secret = os.getenv("CLOUDINARY_API_SECRET", "").strip()

if USE_CLOUDINARY:
    if _cloudinary_url and not _cloudinary_url.startswith("cloudinary://"):
        raise ImproperlyConfigured(
            "CLOUDINARY_URL must start with 'cloudinary://'. Remove the invalid value or replace it with a valid Cloudinary URL."
        )
    if not _cloudinary_url and not (_cloudinary_cloud_name and _cloudinary_api_key and _cloudinary_api_secret):
        raise ImproperlyConfigured(
            "Cloudinary is enabled but credentials are missing. Set CLOUDINARY_URL or CLOUDINARY_CLOUD_NAME/CLOUDINARY_API_KEY/CLOUDINARY_API_SECRET."
        )

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-change-me")
# Default DEBUG to off for safer production behavior.
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"
_default_hosts = "localhost,127.0.0.1" if DEBUG else "*"
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", _default_hosts).split(",") if host.strip()]
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "accounts",
    "theses",
    "search",
]

if USE_CLOUDINARY:
    try:
        import cloudinary  # noqa: F401
    except ImportError as exc:
        raise ImproperlyConfigured(
            "USE_CLOUDINARY=1 requires packages 'cloudinary' and 'django-cloudinary-storage'."
        ) from exc

    INSTALLED_APPS += ["cloudinary_storage", "cloudinary"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "elibrary.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "search.context_processors.search_ui_context",
            ],
        },
    },
]

WSGI_APPLICATION = "elibrary.wsgi.application"
ASGI_APPLICATION = "elibrary.asgi.application"

_database_url = os.getenv("DATABASE_URL")
if _database_url:
    DATABASES = {"default": dj_database_url.parse(_database_url, conn_max_age=600)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
_static_dir = BASE_DIR / "static"
STATICFILES_DIRS = [_static_dir] if _static_dir.exists() else []
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"

# Use Railway persistent volume when available, else local media directory.
if os.getenv("RAILWAY_ENVIRONMENT"):
    MEDIA_ROOT = Path(os.getenv("DJANGO_MEDIA_ROOT", "/data/media"))
else:
    MEDIA_ROOT = Path(os.getenv("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media")))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"
X_FRAME_OPTIONS = "DENY"

# Upload tuning for large thesis PDFs: stream to temp files instead of keeping payloads in memory.
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("FILE_UPLOAD_MAX_MEMORY_SIZE", 1024 * 1024))
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DATA_UPLOAD_MAX_MEMORY_SIZE", 50 * 1024 * 1024))

# If a thesis PDF exceeds this size, download view falls back to a direct file URL redirect.
THESIS_DOWNLOAD_PROXY_MAX_MB = int(os.getenv("THESIS_DOWNLOAD_PROXY_MAX_MB", 25))

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticatedOrReadOnly"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
}

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

if USE_CLOUDINARY:
    STORAGES = {
        "default": {"BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
elif USE_S3:
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "")
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "us-east-1")
    AWS_S3_CUSTOM_DOMAIN = os.getenv("AWS_S3_CUSTOM_DOMAIN", "")
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
        "staticfiles": {"BACKEND": "storages.backends.s3boto3.S3StaticStorage"},
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@elibrary.local")

ELIBRARY_SOURCE_LINKS = [
    {
        "label": "Free E-Library",
        "url": os.getenv("FREE_ELIBRARY_URL", "https://data.adb.org/dataset/green-and-blue-bond-impact-report"),
    },
    {
        "label": "G-Drive Manuscripts",
        "url": os.getenv("GDRIVE_LIBRARY_URL", ""),
    },
    {
        "label": "OATD (Open Access Theses and Dissertations)",
        "url": "https://oatd.org/",
    },
    {
        "label": "NDLTD Global ETD Search",
        "url": "https://ndltd.org/",
    },
    {
        "label": "OpenThesis",
        "url": "http://www.openthesis.org/",
    },
    {
        "label": "ERIC Education Resources",
        "url": "https://eric.ed.gov/",
    },
    {
        "label": "CORE (Open Access Research)",
        "url": "https://core.ac.uk/",
    },
    {
        "label": "BASE Academic Search",
        "url": "https://www.base-search.net/",
    },
    {
        "label": "DOAJ Journals",
        "url": "https://doaj.org/",
    },
    {
        "label": "UNESCO Digital Library",
        "url": "https://unesdoc.unesco.org/",
    },
    {
        "label": "World Bank Open Knowledge Repository",
        "url": "https://openknowledge.worldbank.org/",
    },
]

ENABLE_SECURITY_HARDENING = os.getenv("DJANGO_ENABLE_SECURITY", "0") == "1"

if not DEBUG and ENABLE_SECURITY_HARDENING:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", 31536000))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    X_FRAME_OPTIONS = "DENY"
