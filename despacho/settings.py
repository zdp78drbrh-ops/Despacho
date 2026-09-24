"""Configuración de Despacho. Todo lo sensible viene de variables de entorno (ver .env.example)."""

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def _env(nombre, defecto=""):
    return os.environ.get(nombre, defecto)


def _env_bool(nombre, defecto=False):
    return _env(nombre, "1" if defecto else "0").lower() in ("1", "true", "si", "sí", "yes")


def _env_lista(nombre, defecto=""):
    return [x.strip() for x in _env(nombre, defecto).split(",") if x.strip()]


DEBUG = _env_bool("DJANGO_DEBUG")
SECRET_KEY = _env("DJANGO_SECRET_KEY") or ("dev-inseguro-no-usar-en-produccion" if DEBUG else "")
if not SECRET_KEY:
    raise RuntimeError("Falta DJANGO_SECRET_KEY")
ALLOWED_HOSTS = _env_lista("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = _env_lista("DJANGO_CSRF_TRUSTED_ORIGINS")
SITIO_URL = _env("SITIO_URL", "http://localhost:8000").rstrip("/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "nucleo",
    "cuentas",
    "auditoria",
    "litigios",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "cuentas.middleware.LoginObligatorioMiddleware",
]

ROOT_URLCONF = "despacho.urls"
WSGI_APPLICATION = "despacho.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
            "builtins": ["litigios.templatetags.despacho"],
        },
    },
]

DATABASES = {
    "default": dj_database_url.config(
        default=_env("DATABASE_URL", "postgres://postgres@localhost:5432/despacho"), conn_max_age=60
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "cuentas.Usuario"
LOGIN_URL = "entrar"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "entrar"
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
# La sesión expira tras 8 horas sin actividad.
SESSION_COOKIE_AGE = 8 * 3600
SESSION_SAVE_EVERY_REQUEST = True
# Bloqueo tras intentos fallidos (cuentas.backends)
AUTHENTICATION_BACKENDS = ["cuentas.backends.BackendConBloqueo"]
INTENTOS_MAXIMOS = 5
MINUTOS_BLOQUEO = 15

LANGUAGE_CODE = "es-mx"
TIME_ZONE = "America/Mexico_City"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_ROOT = BASE_DIR / "media"

# Archivos PDF: S3 privado si está configurado; disco local en desarrollo.
if _env("S3_BUCKET"):
    _pdf = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": _env("S3_BUCKET"),
            "endpoint_url": _env("S3_ENDPOINT_URL") or None,
            "region_name": _env("S3_REGION") or None,
            "access_key": _env("S3_ACCESS_KEY"),
            "secret_key": _env("S3_SECRET_KEY"),
            "default_acl": "private",
            "querystring_auth": True,
            "querystring_expire": 300,
            "file_overwrite": False,
        },
    }
else:
    _pdf = {"BACKEND": "django.core.files.storage.FileSystemStorage", "OPTIONS": {"location": MEDIA_ROOT}}
STORAGES = {
    "default": _pdf,
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}
PDF_TAMANO_MAXIMO = 50 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

if _env("EMAIL_HOST_PASSWORD"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = _env("EMAIL_HOST", "smtp.resend.com")
    EMAIL_PORT = int(_env("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = _env("EMAIL_HOST_USER", "resend")
    EMAIL_HOST_PASSWORD = _env("EMAIL_HOST_PASSWORD")
    EMAIL_USE_TLS = True
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = _env("DEFAULT_FROM_EMAIL", "Despacho <sistema@localhost>")

RESPALDO = {
    "bucket": _env("RESPALDO_BUCKET"),
    "endpoint_url": _env("RESPALDO_ENDPOINT_URL") or None,
    "access_key": _env("RESPALDO_ACCESS_KEY"),
    "secret_key": _env("RESPALDO_SECRET_KEY"),
}

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = _env_bool("DJANGO_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
