"""
Django settings for core project.
"""
from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# --- Básicos ---
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-not-safe")  # ← ya no hardcodees aquí
DEBUG = os.getenv("DEBUG", "on").lower() in ("1", "true", "on", "yes")

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"]

# Apps
INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "rest_framework",
    "accounts.apps.AccountsConfig",
    'django_extensions',
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.AuditWriteMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

# --- DB (mueve credenciales a .env si quieres) ---
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'bv9ayegygncnd2trj7ae',  
        'USER': 'uildoutw8oxppefm',     
        'PASSWORD': 'cmCHfpJ1f5ZMl4oXnfOo',  
        'HOST': 'bv9ayegygncnd2trj7ae-mysql.services.clever-cloud.com', 
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'ssl': {'ca': None}  
        }
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# i18n
LANGUAGE_CODE = "es"
USE_I18N = True
TIME_ZONE = "America/La_Paz"
USE_TZ = True

# Static
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Auth redirects
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

# Custom user
AUTH_USER_MODEL = "accounts.User"

# Precio unitario de galleta (Bs)
COOKIE_UNIT_PRICE_BS = float(os.getenv("COOKIE_UNIT_PRICE_BS", "10"))

# --- Stripe desde .env (sin hardcode) ---
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Moneda & dominio
CURRENCY = os.getenv("CURRENCY", "BOB")
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")
