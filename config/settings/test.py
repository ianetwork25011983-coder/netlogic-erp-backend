"""
Settings para `pytest` / `manage.py test`.

Usa SQLite en memoria por velocidad. Las migraciones de la Fase 1 usan
`UniqueConstraint(nulls_distinct=False)`, pensado para Postgres 15+; en
SQLite también funciona (probado), así que no hace falta tener Postgres
levantado solo para correr la suite de tests. Si Jorge prefiere testear
contra el motor real, puede sobreescribir `DATABASES` acá apuntando a un
Postgres de test.

Los `os.environ.setdefault(...)` van ANTES de importar `base.py` (que es
quien realmente lee estas variables vía `python-decouple`) para no
depender de un archivo `.env` real solo para poder correr la suite de
tests — los valores son dummies, nunca hay una conexión real a
Postgres/Redis durante los tests.
"""
import os

os.environ.setdefault("DJANGO_SECRET_KEY", "clave-secreta-solo-para-tests-no-usar-en-produccion")
os.environ.setdefault("DJANGO_DEBUG", "False")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("DB_USER", "test_user")
os.environ.setdefault("DB_PASSWORD", "test_password")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "")

from .base import *  # noqa: F401,F403,E402

DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # mucho más rápido solo para tests

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

LOGGING["loggers"]["django"]["level"] = "WARNING"  # noqa: F405
