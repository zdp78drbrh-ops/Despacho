from django.conf import settings
from django.db import models


class EventoAuditoria(models.Model):
    """Registro inmutable. La base de datos rechaza UPDATE/DELETE/TRUNCATE y sella cada fila con un hash
    encadenado al de la anterior (ver migración 0002). `fecha`, `id` y los hashes los asigna la base."""

    fecha = models.DateTimeField(null=True, blank=True, db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    usuario_nombre = models.CharField(max_length=120, blank=True, default="")
    ip = models.GenericIPAddressField(null=True, blank=True)
    accion = models.CharField(max_length=40, db_index=True)
    entidad = models.CharField(max_length=40, db_index=True)
    entidad_id = models.CharField(max_length=40, blank=True, default="", db_index=True)
    descripcion = models.TextField(blank=True, default="")
    datos = models.JSONField(default=dict, blank=True)
    hash_anterior = models.CharField(max_length=64, blank=True, default="")
    hash = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ["-id"]
        verbose_name = "evento de auditoría"
        verbose_name_plural = "eventos de auditoría"

    def __str__(self):
        return f"{self.fecha:%Y-%m-%d %H:%M} {self.usuario_nombre} {self.accion} {self.entidad} {self.entidad_id}"
