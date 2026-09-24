"""Único punto de escritura de la auditoría. Se llama dentro de la misma transacción que el cambio."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from django.db import connection
from django.db.models import FileField, ForeignKey

from .models import EventoAuditoria


@dataclass
class Actor:
    usuario: object = None
    ip: str | None = None

    @classmethod
    def de(cls, request, anonimo=False):
        if request is None:
            return cls()
        ip = (
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR")
            or None
        )
        u = getattr(request, "user", None)
        return cls(usuario=None if anonimo or not (u and u.is_authenticated) else u, ip=ip)

    @property
    def nombre(self):
        return self.usuario.nombre if self.usuario else "Sistema"


def _valor(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    return v


def foto(obj):
    """Diccionario serializable con los campos propios del objeto (para el antes/después)."""
    d = {}
    for f in obj._meta.concrete_fields:
        if isinstance(f, ForeignKey):
            d[f.name] = getattr(obj, f.attname)
        elif isinstance(f, FileField):
            d[f.name] = getattr(obj, f.name).name or ""
        else:
            d[f.name] = _valor(getattr(obj, f.name))
    return d


def diferencias(antes, despues):
    return {k: [antes.get(k), v] for k, v in despues.items() if antes.get(k) != v}


def auditar(actor, accion, obj=None, *, entidad=None, entidad_id=None, datos=None, descripcion=""):
    actor = actor or Actor()
    return EventoAuditoria.objects.create(
        usuario=actor.usuario,
        usuario_nombre=actor.nombre,
        ip=actor.ip,
        accion=accion,
        entidad=entidad or (obj._meta.model_name if obj is not None else ""),
        entidad_id=str(entidad_id if entidad_id is not None else (obj.pk if obj is not None else "")),
        descripcion=descripcion[:2000],
        datos=datos if datos is not None else {},
    )


def verificar_cadena():
    """Devuelve None si la cadena está íntegra, o el id del primer evento alterado."""
    with connection.cursor() as c:
        c.execute("SELECT auditoria_verificar()")
        return c.fetchone()[0]
