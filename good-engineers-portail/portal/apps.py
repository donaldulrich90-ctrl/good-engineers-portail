from django.apps import AppConfig


class PortalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "portal"
    verbose_name = "Portail GOOD ENGINEERS"

    def ready(self):
        from . import signals  # noqa: F401
