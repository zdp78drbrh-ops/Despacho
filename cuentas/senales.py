from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from auditoria.servicios import Actor, auditar


@receiver(user_logged_in)
def _entro(sender, request, user, **kw):
    auditar(Actor.de(request), "iniciar_sesion", user)


@receiver(user_logged_out)
def _salio(sender, request, user, **kw):
    if user:
        auditar(Actor.de(request), "cerrar_sesion", user)


@receiver(user_login_failed)
def _fallo(sender, credentials, request=None, **kw):
    auditar(
        Actor.de(request, anonimo=True),
        "acceso_fallido",
        None,
        entidad="usuario",
        datos={"correo": (credentials or {}).get("username", "")},
    )
