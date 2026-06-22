from django.apps import AppConfig


class AutomationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.automation"
    verbose_name = "Automatizaciones (Motor de Reglas)"

    def ready(self):
        from . import signals  # noqa: F401
