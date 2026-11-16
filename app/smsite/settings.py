"""Софтмонтаж — серверная часть сайта (каталог оборудования).

Настройки берутся из переменных окружения (на сервере — файл /opt/softmontazh/.env,
его читает systemd). Без переменных запускается локально: SQLite, DEBUG.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SITE_ROOT = BASE_DIR.parent  # корень статического сайта (index.html, assets/, brand/)

env = os.environ.get
SECRET_KEY = env("SM_SECRET_KEY", "dev-only-not-secret")
DEBUG = env("SM_DEBUG", "1" if not env("SM_SECRET_KEY") else "0") == "1"
ALLOWED_HOSTS = [h for h in env("SM_ALLOWED_HOSTS", "softmontazh.kz,localhost,127.0.0.1").split(",") if h]
CSRF_TRUSTED_ORIGINS = ["https://softmontazh.kz"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "catalog",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "smsite.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "smsite.wsgi.application"

if env("SM_DB_NAME"):
    # PostgreSQL через локальный сокет, вход по имени системного пользователя (peer) — без пароля
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("SM_DB_NAME"),
        "USER": env("SM_DB_USER", env("SM_DB_NAME")),
        "HOST": env("SM_DB_HOST", ""),
        "CONN_MAX_AGE": 60,
    }}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "ru"
TIME_ZONE = "Asia/Almaty"
USE_I18N = True
USE_TZ = True

# Статика админки Django (собирается collectstatic, отдаёт nginx)
STATIC_URL = "/dj-static/"
STATIC_ROOT = env("SM_STATIC_ROOT", str(BASE_DIR / "_static"))

# Временные файлы импорта
SM_DATA_DIR = Path(env("SM_DATA_DIR", str(BASE_DIR / "_data")))

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {"catalog": {"handlers": ["console"], "level": "INFO", "propagate": False}},
}
