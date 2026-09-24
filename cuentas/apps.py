from django.apps import AppConfig


class CuentasConfig(AppConfig):
    name = "cuentas"
    verbose_name = "Cuentas"

    def ready(self):
        from . import senales  # noqa: F401
