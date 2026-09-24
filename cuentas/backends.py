from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.utils import timezone


class BackendConBloqueo(ModelBackend):
    """Bloquea la cuenta MINUTOS_BLOQUEO minutos después de INTENTOS_MAXIMOS contraseñas incorrectas."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        Usuario = get_user_model()
        email = (username or kwargs.get("email") or "").strip().lower()
        u = Usuario.objects.filter(email=email).first()
        if u is None:
            Usuario().set_password(password)  # tiempo constante
            return None
        ahora = timezone.now()
        if u.bloqueado_hasta and u.bloqueado_hasta > ahora:
            return None
        if u.check_password(password) and self.user_can_authenticate(u):
            if u.intentos_fallidos:
                u.intentos_fallidos = 0
                u.bloqueado_hasta = None
                u.save(update_fields=["intentos_fallidos", "bloqueado_hasta"])
            return u
        u.intentos_fallidos += 1
        if u.intentos_fallidos >= settings.INTENTOS_MAXIMOS:
            u.bloqueado_hasta = ahora + timedelta(minutes=settings.MINUTOS_BLOQUEO)
            u.intentos_fallidos = 0
        u.save(update_fields=["intentos_fallidos", "bloqueado_hasta"])
        return None
